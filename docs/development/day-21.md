# Day 21 - Ownership-Chain Enforcement Retrofit

## Objective

Close the live IDOR vulnerability documented in Day 20's "KNOWN CRITICAL
GAP": every Day 15-19 router accepts a client-supplied `workspace_id`/
`profile_id` (query or path parameter) and trusts it at face value, with
no verification that the authenticated caller (Day 20's JWT identity)
actually belongs to that workspace or owns that profile. `WorkspaceMember
.user_id` is a bare, unenforced `String(255)` with no foreign key to
`User.id`. This day retrofits real ownership-chain enforcement onto every
existing router without changing any route's URL shape, request/response
schema, or business behavior for a legitimately-authorized caller.

Full architectural rule (already stated in `CLAUDE.md` /
`docs/product/product-architecture.md`, not introduced by this day):
a mismatch at any level of `Authenticated User -> Workspace Membership ->
Workspace -> ContentProfile -> Resource` returns **404, never 403/400**,
so cross-tenant resource existence is never leaked.

## Scope

In scope:

- A proper FK `WorkspaceMember.user_id -> User.id` (replacing the bare
  string column).
- Two reusable FastAPI dependencies, `require_workspace_access` and
  `require_profile_access`, that perform the real ownership check.
- Wiring those dependencies into every Day 15-19 router that accepts a
  `workspace_id`/`profile_id`.
- Updating existing functional tests to authenticate as the correct
  owning user (tests written before Day 20 have no auth at all).
- Per-router regression coverage proving User A cannot reach User B's
  workspace/profile-scoped data.
- Dependency-level unit tests for the two new dependencies.

Explicitly out of scope (future-day work, not touched here):

- Multi-workspace-per-user switching UX (the dependency is written to
  support it later via a real `(user_id, workspace_id)` lookup, but no
  such feature is added).
- Role-based authorization within a workspace (owner vs. admin vs.
  member) — `require_workspace_access` only checks membership exists, not
  role. No route currently branches on role.
- Any change to a route's URL, request schema, or response schema.
- Any change to business logic, scoring, or generation behavior.

## Implementation

### `WorkspaceMember.user_id` foreign key

Migration `w6x7y8z9a0` (down-revision `v5w6x7y8z9`, the Day 20 head)
converts `workspace_members.user_id` from `String(255)` to `UUID`, adds
`fk_workspace_members_user_id_users` (`ON DELETE CASCADE`), and adds a
composite index `ix_workspace_members_user_id_workspace_id` on
`(user_id, workspace_id)` — the exact shape `require_workspace_access`
queries on. On PostgreSQL the upgrade first runs a `DO $$ ... $$` guard
that raises loudly if any existing row's `user_id` isn't a well-formed
UUID matching a real `users.id` row, rather than silently coercing or
dropping it — per this day's intent, such a row must be fixed manually.
On SQLite (the test database) the column swap runs through
`op.batch_alter_table` with no such guard, since the test convention has
no real pre-existing data to validate. Reversible.

### `app/authz/dependencies.py` (new module)

```python
async def require_workspace_access(
    workspace_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceMember:
    ...  # 404 if no WorkspaceMember row for (current_user.id, workspace_id)

async def require_profile_access(
    profile_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentProfile:
    ...  # 404 if profile doesn't exist or belongs to a different workspace
```

- `require_workspace_access` depends on Day 20's `get_current_user` (JWT
  verification) and performs a genuine, indexed `(user_id, workspace_id)`
  query — never a hardcoded single-workspace shortcut — returning the
  `WorkspaceMember` row on success. FastAPI auto-binds `workspace_id`
  from whichever request location (path or query) the calling route
  already declares.
- `require_profile_access` composes `require_workspace_access` (rather
  than re-checking membership itself) and additionally verifies the
  requested `profile_id` belongs to that same workspace.
- Both raise 404 uniformly — a nonexistent workspace, a workspace the
  caller isn't a member of, and a profile belonging to a different
  workspace are all indistinguishable 404s from the outside.

### Router retrofit

Every Day 15-19 router that previously accepted `workspace_id`/
`profile_id` as a bare, unverified parameter now depends on
`require_workspace_access` or `require_profile_access` instead (whichever
matches the resource's position in the ownership chain), and reads the
verified `workspace_id`/`profile_id` off the returned `WorkspaceMember`/
`ContentProfile` rather than off the raw client input:

`audience_intelligence`, `audience_objections`, `audience_questions`,
`audience_signals`, `brands`, `business_context`, `competitors`,
`content_briefs`, `content_draft_variations`, `content_drafts`,
`content_evaluations`, `content_intelligence_synthesis`,
`content_library`, `content_opportunities`, `content_profiles`,
`desires`, `intelligence_analysis`, `market_intelligence`,
`market_signals`, `offers`, `pain_points`, `performance`, `personas`,
`products`, `published_content`, `services`, `topics`, `workspaces`.

`POST /workspaces` (workspace creation) is deliberately left
undependent — no `WorkspaceMember` row exists yet at creation time, so
there is nothing to check ownership against; the caller becomes the
workspace's first member as a result of the call. Every other
`/workspaces/{id}` route (`GET`/`PATCH`/`DELETE`) depends on
`require_workspace_access`.

A genuine, pre-existing production regression was found and fixed in the
same pass: `app/api/v1/content_opportunities.py`'s `list_opportunities`
carried a stray `sort_by` parameter (from an earlier, unrelated edit)
that `ContentOpportunityRepository.list_by_profile()` does not accept,
raising a `TypeError` at runtime. It only surfaced once the corresponding
test could execute far enough (past the newly-enforced auth layer) to
reach it; confirmed as a genuine regression (not pre-existing) by
checking the same test against pre-Day-21 `develop` HEAD, where it
passed. Removed the stray parameter and its passthrough — no behavior
change beyond removing dead code that was never reachable from any real
client request (no schema/route exposed `sort_by` on this endpoint).

### Test retrofit

Every existing Day 15-19 functional test that exercises a workspace- or
profile-scoped route now authenticates as the correct owning user before
making the request, via a new `tests/conftest.py` helper:

```python
async def authenticate_as_workspace_owner(
    client: AsyncClient, db_session: AsyncSession, workspace_id: uuid.UUID
) -> User:
    ...  # seeds a User + owning WorkspaceMember row, mints a JWT,
         # sets it as the client's default Authorization header
```

Each call creates a fresh, distinct `User` — used deliberately in
cross-tenant isolation tests to simulate "a different authenticated
user," not just "a different workspace."

Ordering matters: setting the client's Authorization header is a global,
destructive mutation of that client instance. Every isolation test that
sets up data in workspace A and workspace B was restructured so all of
workspace A's HTTP calls (including any further setup) complete while
still authenticated as A's owner, before switching to B's owner — not
immediately after each workspace's creation, which would leave later
same-workspace calls incorrectly returning 404.

Retrofitted and passing this day (function-level, actually run via
`uv run pytest`, not assumed): `test_audience_intelligence.py`,
`test_audience_objections.py`, `test_audience_questions.py`,
`test_audience_signals.py`, `test_brands.py`, `test_competitors.py`,
`test_content_briefs.py`, `test_content_opportunities.py`,
`test_content_profiles.py`, `test_desires.py`,
`test_market_intelligence.py`, `test_market_signals.py`,
`test_pain_points.py`, `test_personas.py`, `test_topics.py`,
`test_content_drafts.py`, `test_content_draft_variations.py`,
`test_content_evaluations.py`, `test_performance.py`,
`test_content_library.py`. `test_business_context.py`, `test_products.py`,
`test_services.py`, and `test_offers.py` needed no changes and pass
unmodified against the retrofitted routers.

### Known remaining work (not completed this day)

- `test_workspaces.py` still fails against the retrofitted
  `app/api/v1/workspaces.py` (5 failures confirmed via `uv run pytest`:
  `GET`/`PATCH`/`DELETE /workspaces/{id}` now correctly return 401 for an
  unauthenticated request that the pre-Day-21 test never authenticated
  for) — needs the same retrofit pattern applied.
- `test_content_intelligence_synthesis.py`, `test_intelligence_analysis.py`,
  `test_published_content.py`, `test_opportunity_reasoning.py`, and
  `test_infrastructure_jobs.py` have not yet been inspected/retrofitted
  this day.
- No per-router "User A cannot access User B's data" regression test has
  been written yet — existing retrofitted tests happen to cover
  cross-workspace 404s for the routers they already tested this way
  pre-Day-21, but there is no dedicated, systematic regression suite
  proving this for every retrofitted router.
- No dependency-level unit test exists yet for `require_workspace_access`
  /`require_profile_access` in isolation (nonexistent workspace, workspace
  the caller isn't a member of, profile belonging to a different
  workspace).
- A full-repository `uv run pytest -q` run (all files) has not been
  completed this day; only the specific files listed above have been run
  and confirmed passing.
- Repo-wide `ruff check`/`ruff format --check` has not been re-run across
  every touched file this day (each retrofitted test file was checked
  individually with `ruff check --fix`/`ruff format` immediately after
  editing it).

Days 15-19 (and now most, but not yet all, of Day 20's own workspace
routes) should be considered ownership-chain-complete once the remaining
items above are closed — see "Day 21 completion" note to be added to this
file, or a follow-up day, once that work lands.

## Migration

- `w6x7y8z9a0` (head, down-revision `v5w6x7y8z9`) — see "WorkspaceMember
  .user_id foreign key" above. Reversible. Single migration head confirmed
  via `uv run alembic heads` -> `w6x7y8z9a0 (head)`.

## Files changed

- New: `app/authz/dependencies.py`, `migrations/versions/w6x7y8z9a0_add_workspace_member_user_fk.py`.
- Modified: `app/models/workspace_member.py` (FK column), every router
  listed under "Router retrofit" above, `app/api/v1/content_opportunities.py`
  (stray `sort_by` regression fix), `tests/conftest.py` (new
  `authenticate_as_workspace_owner` helper), and every test file listed
  under "Test retrofit" above as retrofitted.
