# Day 22 - Registration & Onboarding (Step-Wise, Workspace-Anchored)

Read and follow:
- `CLAUDE.md`
- `docs/product/product-architecture.md` (Universal Content Profile,
  Business Context, Identity/Tenancy/Authorization)
- `docs/development/progress.md` (Day 2/3 - Workspace, WorkspaceMember,
  ContentProfile; Day 16 - Brand/Audience Intelligence structures; Day 20
  - User model, password hashing, JWT issuance; Day 21 - ownership-chain
  pattern and ContentProfile/Workspace FK)

## Terminology guardrail

`ContentProfile` is the workspace's content-strategy identity (brand,
audience, goals, what content should be generated) - it belongs to the
`Workspace`, never to the `User`, and it is NEVER a personal user profile.
No field, variable, table, or endpoint name implies `ContentProfile`
represents who the person is. No `user_id` column was added to
`ContentProfile`. Nothing is named `CreatorProfile`.
`ContentProfile.type = "creator"` (the existing `ContentProfileType` enum
value describing the KIND OF CONTENT STRATEGY) is not conflated with any
notion of a creator's personal identity - unrelated concepts that happen
to share the word "creator." A separate, not-yet-built per-user personal
profile concept (for future multi-member workspaces) is out of scope for
this day and was not introduced, stubbed, or hinted at. `ContentProfile`
remains addressable by `workspace_id` alone, never by `user_id`.

## Scope correction vs. an earlier circulated onboarding spec

An earlier spec called for "one primary onboarding command" (a single
end-of-flow submission) while also requiring
`NOT_STARTED`/`IN_PROGRESS`/`COMPLETED` states and resume behavior. Those
requirements contradict each other - a single end-of-flow submission has
nothing to persist mid-flow to actually resume. Per product decision,
this day implements **step-wise persistence** instead: each step is its
own request that saves immediately. This supersedes the single-command
design; everything else about the five information areas, validation,
and out-of-scope boundaries from that earlier spec still applies.

## Model A: multiple profiles per workspace

Per product decision, a `Workspace` is not limited to one `ContentProfile`
- one user may eventually run multiple distinct content personas (e.g. a
football-tactics persona and a separate memes persona) under a single
account. No unique constraint limits a `Workspace` to one `ContentProfile`.
Inspection at the start of this day confirmed Day 2/3 never added such a
constraint, so no schema change was needed to satisfy this. This day
still only builds the flow for a workspace's **first** profile
(registration + onboarding) - creating additional profiles later is
explicitly out of scope (see "Out of scope" below), but the schema does
not architecturally block it.

## Objective

Registration creates a `User`, auto-provisions a `Workspace` with that
user as its sole `WorkspaceMember` (owner role), and issues tokens
immediately. Onboarding is a step-wise, resumable flow that progressively
builds the workspace's `ContentProfile` (`type=creator`), with
`onboarding_status` living on `Workspace` (not `ContentProfile`) since it
must be checkable before any profile exists.

## Section 1 - Registration

In scope:

- `POST /api/v1/auth/register`: email + password -> creates `User` (Day
  20 hashing), creates `Workspace`, creates `WorkspaceMember`
  (`role=WorkspaceRole.OWNER` - the existing Day 2 enum value; no new
  "owner" value was needed), sets `Workspace.onboarding_status =
  NOT_STARTED`, issues access + refresh tokens immediately by reusing Day
  20's issuance logic directly (`AuthService._issue_token_pair`).
- Duplicate-email rejection without creating duplicate records: a
  pre-check plus an `IntegrityError` catch on the race case, both
  normalized to the same `EmailAlreadyRegisteredError` -> `409`.
- `/auth/register` registered under the Day 15/20 rate-limiting pattern
  (`RouteCategory.AUTH_REGISTER`, exact-path match, its own settings).

Out of scope: signup UI, email verification, OAuth signup, second/later
profile creation for an already-onboarded workspace.

## Section 2 - Onboarding (step-wise)

In scope:

- `Workspace.onboarding_status` column: `NOT_STARTED` | `IN_PROGRESS` |
  `COMPLETED`.
- `get_current_workspace() -> Workspace` (new dependency in
  `app/authz/dependencies.py`, built on Day 20's `get_current_user`):
  resolves the authenticated user's workspace via their `WorkspaceMember`
  row with **no `workspace_id` parameter accepted from the client at
  all** - there is nothing to verify against a client-supplied id here,
  since onboarding never lets the client specify which workspace it
  means. A genuine membership-lookup query, matching Day 21's pattern,
  not a shortcut.
- Step endpoints (each independently persisted via `PUT`):
  - `/api/v1/onboarding/identity` - name, positioning, primary niche,
    topics, expertise. Creates `ContentProfile` (`type=creator`) on
    first call if none exists for this workspace; updates on subsequent
    calls.
  - `/api/v1/onboarding/audience` - target audience description,
    interests, pain points/questions. Maps into existing Day 16 Audience
    Intelligence structures (`AudienceIntelligence.summary`/
    `psychographics`, `PainPoint`, `AudienceQuestion`) - no parallel
    onboarding-only model was created.
  - `/api/v1/onboarding/goals` - growth/authority/engagement/community
    (multi-select), using `ContentProfile.goals` (Day 2/3's existing
    goal representation).
  - `/api/v1/onboarding/brand` - tone, style, things to avoid. Maps into
    the existing Day 16 `Brand` structure (`tone`, `messaging_guidelines`).
  - `/api/v1/onboarding/platforms` - selected platforms (Instagram,
    TikTok, YouTube, Facebook, X, LinkedIn). Context/intent data only -
    no OAuth, no connection (that's Day 23, entirely separate).
  - Each step: resolve workspace via `get_current_workspace()`, validate
    payload, upsert the relevant `ContentProfile` slice, set
    `onboarding_status = IN_PROGRESS` if not already past that, return
    the updated slice.
- `GET /api/v1/onboarding`: returns current `onboarding_status` and
  whatever partial `ContentProfile`/`Brand`/`AudienceIntelligence` data
  exists, so the frontend can resume exactly where the user left off,
  including across devices (real server state, always re-queried rather
  than read from a possibly-stale in-memory relationship).
- `POST /api/v1/onboarding/complete`: validates all required fields
  across all five areas are present (the actual completeness gate -
  individual steps allow partial saves), sets
  `onboarding_status = COMPLETED`, returns the finished profile.
- `BusinessContext` remains null throughout - never required, never
  prompted for, never touched by any onboarding step.

Out of scope (carried forward unchanged from the original onboarding
spec): AI onboarding assistant, AI-generated profile/personas, automatic
market research, trend discovery, opportunity generation, `ContentBrief`
generation, content drafts/hooks/captions/scripts, image/video
generation, publishing, scheduling, social account connections/OAuth
(Day 23), analytics, performance measurement, learning engine, RAG,
agents, notifications, creator monetization, business products/services/
offers. Also out of scope: automatically triggering any Day 16-18 AI
reasoning task (`brand_analysis`, `audience_analysis`, `market_analysis`,
`strategic_synthesis`) at onboarding completion - those stay triggered
the way Days 16-18 already specify; onboarding establishes the data, it
does not itself invoke reasoning over it.

**Model A note**: creating a second or subsequent `ContentProfile` within
an already-onboarded workspace, profile switching, and per-profile
plan-limit enforcement are out of scope - the data model allows multiple
profiles per workspace (no one-profile-per-workspace constraint), but
building the actual flow to create/manage additional profiles is a
separate, future day.

## Schema deviations (confirmed with the product owner before implementation)

Two fields the spec asks for have no existing home in the Day 2/3/16
schema, so a strict "no `ContentProfile` schema change" reading would
have silently dropped them. Both were resolved as small, additive,
nullable columns rather than overloading an existing field:

- **`ContentProfile.primary_niche`** (`String(255)`, nullable): the
  identity step's "primary niche" has no existing column
  (`topics`/`expertise`/`goals` are lists, not a single niche
  statement). Rejected alternative: folding it into `topics[0]` by
  convention, which would have made "primary niche" silently
  unrecoverable as a distinct concept from "topics."
- **`ContentProfile.platforms`** (JSON list, nullable): the platforms
  step's selected distribution platforms have no home anywhere in the
  existing schema (`ContentProfile`, `Brand`, `AudienceIntelligence`) -
  this is genuinely new onboarding-only intent data, not a case of
  reusing an existing sibling structure.

Both are additive, nullable, and added in the same migration as
`Workspace.onboarding_status`.

## System design

- `Workspace` gets an `onboarding_status` enum column (default
  `NOT_STARTED`); no other `ContentProfile` schema change beyond the two
  deviations above and what Days 2/3/16 already defined.
- `get_current_workspace()` is a single indexed `WorkspaceMember` lookup,
  same performance profile as Day 21's dependencies, not cached.
- **Model A**: no unique constraint limits a `Workspace` to one
  `ContentProfile` - confirmed absent by inspection, so nothing needed
  removing.
- Idempotency is scoped to "the profile currently being onboarded," not
  "the workspace's only profile" - duplicate step submissions update
  that one profile in place (matched as the workspace's first/only
  profile), and duplicate registration attempts must not create a second
  `Workspace` (enforced via the pre-check + `IntegrityError` fallback).

## Architecture

New `app/onboarding/` module (`schemas.py`, `service.py`, `router.py`),
reusing `ContentProfileService`/`ContentProfileRepository` (Days 2/3),
`AudienceIntelligenceService`/`PainPointService`/`AudienceQuestionService`
(Day 4), and `BrandService` (Day 3) for actual persistence - no
duplicate profile-write logic. `get_current_workspace()` lives alongside
Day 21's `require_workspace_access`/`require_profile_access` in
`app/authz/`. Registration lives in `app/auth/` alongside Day 20's
login/refresh/logout - account-lifecycle logic and onboarding logic stay
in separate modules even though they ship together.

## Security

Registration derives `WorkspaceMember` ownership from the newly created
`User` only, never a client-supplied identifier. Onboarding step
endpoints use `get_current_workspace()` exclusively - none accept a
`workspace_id` from the client, not even to validate against.

## Testing

Registration creates exactly one `User`/`Workspace`/`WorkspaceMember`
(owner) with valid tokens; duplicate-email rejected without duplicate
records (including a case-insensitivity check); rate limiting on
`/auth/register`; unauthenticated onboarding requests rejected; each
step persists and is retrievable via `GET`; out-of-order step submission
(audience before identity) rejected with 400 per the identity-first
rule; resubmitting a step updates in place, no duplicates; `/complete`
rejects on missing required fields and succeeds when complete; resumed
session (fresh request, same token) sees prior partial data;
`BusinessContext` confirmed null on completion; cross-user isolation
tested directly (User A cannot view/modify User B's onboarding by any
means); full regression on Days 15-21.

## Definition of Done

Registration and onboarding function end-to-end per the checklist above;
no unique constraint limits a `Workspace` to one `ContentProfile` (Model
A, verified by inspection); no `workspace_id` ever accepted as a
client-supplied parameter anywhere in this day's endpoints; cross-user
isolation verified directly; full Days 15-21 regression suite passes
**unchanged** - see "Day 21 scope note" below for what "unchanged" means
in practice; `progress.md` updated; migration applied and reversible;
Ruff clean for every file this day touched.

### Day 21 scope note

A full baseline run at the start of this day showed **28 pre-existing
test failures**, all tracked under Day 21's own "Remaining work" section
in `progress.md` (`test_workspaces.py`, `test_intelligence_analysis.py`,
`test_published_content.py`, `test_content_intelligence_synthesis.py`) -
none in a file this day touches. Closing those is Day 21 scope, not Day
22's. "Full Days 15-21 regression suite passes unchanged" is therefore
satisfied as: the failing-test count and identity is unchanged by this
day's work (still exactly those 28, still only those 28), not as "zero
failures" - that remains open, tracked Day 21 work. This was confirmed
with the product owner before proceeding rather than assumed.

## Implementation note

See the "Day 22 - Registration & Onboarding" section in
`docs/development/progress.md` for the executed implementation detail,
files changed, migration id, and test results.
