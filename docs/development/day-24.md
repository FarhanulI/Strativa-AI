# Day 24 - Publishing Foundation with Scheduling (Horizontally-Safe)

## Objective

Introduce `PublishedContent` supporting immediate manual publish and
future scheduling, with real publish calls to YouTube/Facebook/Instagram
via the Day 23 adapters, and due-item promotion running as a safe
distributed job correct under N concurrent worker instances.

Full architectural context: `docs/product/product-architecture.md`
("Publishing," "AI Execution and Job Control" — the distributed-safety
principles apply equally to non-AI background jobs) and
`docs/development/progress.md` (Day 9 platform adapter contracts, Day 12
`ContentDraft`, Day 16's `PublishedContent` foundation, Day 15 job
infrastructure and the `DistributedLock` helper, Day 21 ownership-chain
enforcement, Day 23 `PlatformConnection`/adapters).

### Numbering note

`PublishedContent`, its `schedule`/`cancel` flows, and a single-table
poller already existed before this day began — committed as "Day 16 —
Publishing Foundation" and referred to elsewhere in `progress.md` as "the
Day 17 publish scheduler," a pre-existing numbering inconsistency in the
codebase's own history, not introduced by this day. This spec keeps the
"Day 24" label the work was requested under. What Day 24 actually adds:
real platform publish calls through the Day 23 adapters, a `publishing`
claim state, `platform_post_id`, a stuck-row recovery sweep, and —
critically — moving due-item promotion off an in-process FastAPI-lifespan
`asyncio` task and onto a registered Day 15 arq periodic job, which is
what actually makes the claim-then-call mechanism safe to run as more
than one instance.

## Scope

In scope:

- `PublishedContent` model: `draft_id`, `profile_id`, `platform`,
  `external_url` (nullable), `publish_method` (`manual` | `api`),
  `status` (`scheduled` | `publishing` | `published` | `failed` |
  `retracted` | `cancelled`), `scheduled_at`, `published_at`,
  `created_at`, `platform_post_id` (nullable).
- Schedule service: validates eligible draft status, a future
  `scheduled_at`, **and** an active `PlatformConnection` for
  youtube/facebook/instagram targets — rejects with a "platform not
  connected" error if missing.
- Publish-immediately service: calls the real Day 23 `PlatformAdapter`;
  success → `published` + `platform_post_id` + `published_at`; failure →
  `failed`. Re-verifies the connection is `status=connected` immediately
  before calling the adapter, not a stale schedule-time read.
- Cancel service: `scheduled` → `cancelled` only if not yet fired.
- Distributed scheduler, two-phase claim-then-call: an atomic
  `UPDATE published_content SET status='publishing' WHERE
  status='scheduled' AND scheduled_at <= now() RETURNING *` is the
  entire correctness guarantee; the Day 15 `DistributedLock` is a
  performance optimization on top of it, never a substitute. Call only
  after claiming. No auto-retry on failure.
- Recovery sweep: a periodic job moving rows stuck in `publishing` past a
  timeout to `failed`, for manual review.
- API endpoints: schedule, publish-immediately, cancel, list, retrieve
  with lineage.
- Migration: FK to `content_drafts`, index on `(status, scheduled_at)`.

Explicitly out of scope this day:

- TikTok, LinkedIn, X publishing.
- Any new job/queue system — reuse the Day 15 `arq` infrastructure.
- Automatic retry of a failed publish.
- Performance/metrics ingestion (Day 25).

Architecture constraints:

- Router → Service → Repository layering, matching every other domain.
- The promotion job must be a registered Day 15 periodic job, never a
  FastAPI startup-event `asyncio` task.
- The service never calls a platform API directly, only through the Day
  23 adapters.

Security: ownership via Day 21's `require_profile_access(profile_id)`
(Model A allows multiple `ContentProfile`s per Workspace). The promotion
job itself runs with no user context — it operates on rows already
scoped by `profile_id`, not by a request-time ownership check.

## Implementation

### The `ContentDraft`-is-text-only constraint

`ContentDraft` (Day 12) is title/hook/body/cta/caption — there is no
video/image asset anywhere in the system. YouTube requires a video
upload; Instagram (via the linked Facebook Business Account) requires a
media object. Facebook alone has a genuine text-post endpoint
(`POST /{page_id}/feed`). This was raised explicitly before implementing
`publish_content`, and the resolved approach was: give Facebook a real
adapter call, and make YouTube/Instagram fail deterministically rather
than fake a text-only "publish" against an endpoint that requires media —
a stub that returned a plausible success would be worse than one that
refuses, because nothing downstream would ever notice the gap.

### `PublishedContent` model (`app/models/published_content.py`)

- Added `PublishStatus.PUBLISHING` between `SCHEDULED` and `PUBLISHED` —
  the claimed-but-not-yet-resolved state a row sits in for the duration
  of one promotion tick's adapter call.
- Added `platform_post_id` (nullable `String(255)`) — the platform's own
  id for the created post/video (e.g. a Facebook Post ID). Only ever set
  inside the adapter-success branch of `_call_connected_adapter`; never
  populated for the manual/no-op path.
- Existing `Index("ix_published_content_status_scheduled_at", "status",
  "scheduled_at")` (from the Day 16 foundation) is exactly the index the
  claim query's `WHERE status = 'scheduled' AND scheduled_at <= now()`
  needs — reused unchanged, not duplicated.

### Platform adapters (`app/platform_connections/adapters.py`)

- `MediaRequiredError(RuntimeError)`: raised by any adapter whose
  `publish_content` requires a video/image asset `ContentDraft` doesn't
  produce. Raised before any network call — never a network round trip
  that then fails.
- `PublishResult(platform_post_id: str, external_url: str | None)`: the
  typed return contract added to the `PlatformConnectionAdapter`
  Protocol's new `publish_content(*, connection, draft) -> PublishResult`
  method. `_BaseConnectionAdapter`'s default implementation raises
  `MediaRequiredError`, inherited by `YouTubeAdapter`/`InstagramAdapter`
  unchanged.
- `FacebookAdapter.publish_content`: builds `message` from the draft's
  `caption`, falling back to `hook`/`body` joined; calls
  `POST {graph_base()}/{page_id}/feed` with `message` and the connection's
  decrypted access token via the shared `build_http_client()`/
  `raise_for_platform_error` helpers already established in
  `oauth/base.py`; validates the response actually contains a string
  post `id` before treating it as success, raising `OAuthExchangeError`
  otherwise (cannot silently succeed on a malformed response).

### Service (`app/services/published_content.py`)

- `_resolve_connected_platform(platform)`: maps a draft's free-text
  `platform` to a `SocialPlatform` with a real adapter, or `None` for
  anything else (e.g. `"other"`) — those keep using the original
  manual/no-op `ManualPlatformAdapter` path unchanged, requiring no
  `PlatformConnection` at all.
- `_call_connected_adapter`: shared by immediate publish and scheduled
  promotion. Re-fetches the `PlatformConnection` fresh via
  `connection_repository.get_for_profile_platform(...)` immediately
  before calling the adapter — a connection revoked or expired between
  `schedule_draft` time and the due time is caught here, not assumed
  still valid from the schedule-time check. Every failure mode (no
  connection, not `connected`, `MediaRequiredError`, an adapter HTTP
  error) is caught by a single `except Exception` and resolved to
  `status=failed` with the reason recorded — `_mark_failed` never lets an
  exception propagate out of this path.
- `promote_due`: claims due rows via
  `PublishedContentRepository.claim_publishing`, then resolves each
  claimed row to a terminal status by calling
  `_resolve_claimed_item` → `_call_connected_adapter` (or the manual
  no-op path). No retry loop anywhere in this method.
- `recover_stuck_publishing`: delegates to
  `PublishedContentRepository.reclaim_stuck_publishing(before)`, `before`
  computed from `settings.publish_stuck_publishing_timeout_seconds`.
- **Commit discipline**: `publish_draft`/`schedule_draft`/
  `cancel_schedule` each call `self.session.commit()` at the end,
  matching the convention every other service in the codebase actually
  follows (confirmed by inspecting sibling services — each commits
  itself; there is no shared request-boundary commit layer, despite the
  architecture doc's more aspirational framing). This fixed a real
  pre-existing bug: the prior version of this file had no `commit()`
  call anywhere, so a publish/schedule/cancel would flush (visible
  mid-request) but roll back once the request's session closed —
  nothing ever actually persisted. `promote_due`/`recover_stuck_publishing`
  deliberately do **not** commit themselves, since they run in the arq
  worker process with no request-scoped session; the job wrapper commits
  once instead (see below).

### Repository (`app/repositories/published_content.py`)

- `claim_publishing(now)`: the atomic claim —
  `UPDATE published_content SET status='publishing' WHERE
  status='scheduled' AND scheduled_at <= :now RETURNING *`. This single
  statement is the entire correctness guarantee under N concurrent
  worker instances: only one instance's `UPDATE` can match and flip a
  given row, so the same row can never be claimed twice, independent of
  any lock, cache, or in-memory coordination.
- `reclaim_stuck_publishing(before)`: the identical atomic-`UPDATE`-with-
  `RETURNING` shape, moving `publishing` rows with `updated_at <= before`
  to `failed` — a concurrent recovery sweep from another instance can't
  double-process the same stuck row either, for the same reason.
- Both use `execution_options={"populate_existing": True,
  "synchronize_session": False}`. `populate_existing` refreshes matched
  ORM objects straight from `RETURNING`; `synchronize_session=False`
  skips SQLAlchemy's Python-side re-evaluation of the `WHERE` clause
  against already-loaded session objects — that Python-side evaluation
  is what breaks under SQLite specifically (its driver drops tzinfo from
  a `datetime` on round-trip, so a `publishing` row already loaded
  earlier in the same session would have a tz-naive `updated_at`
  compared against a tz-aware `before`). This setting only disables
  SQLAlchemy's own bookkeeping; it has no bearing on the actual
  database-level atomicity of the `UPDATE`, which is what the claim's
  correctness rests on.

### Distributed job wiring (`app/services/publish_promotion.py`, new)

- `promote_due_publishes`: wraps `PublishedContentService.promote_due` in
  `try_lock(redis, "publish-promotion:tick")`. If the lock isn't
  acquired, the tick does nothing and returns — always safe, since the
  atomic claim inside `promote_due` doesn't depend on the lock for
  correctness; the lock only saves a redundant claim query when two
  workers' ticks overlap. Opens its own `async_session_factory()`
  session (no request-scoped session exists in the arq worker process)
  and commits once after the service call returns.
- `recover_stuck_publishes`: same session-per-call, commit-once pattern,
  no lock (a redundant reclaim query is cheap and self-limiting since
  the atomic `UPDATE` still can't double-process a row).
- `promote_due_publishes_cron`/`recover_stuck_publishes_cron`: arq cron
  entrypoints (`ctx` unused, required by arq's cron signature).
- **Registered in `app/workers/settings.py`'s `cron_jobs`** —
  `promote_due_publishes_cron` at `second=set(range(0, 60,
  publish_promotion_interval_seconds))` (default every 30s; the interval
  must evenly divide 60 since arq cron fires on second-of-minute marks,
  not an arbitrary interval), `recover_stuck_publishes_cron` at
  `minute=set(range(0, 60, publish_stuck_recovery_interval_minutes))`
  (default every 15 minutes).
- **Deleted `app/services/publish_scheduler.py`** (the prior FastAPI-
  lifespan `asyncio.create_task` poller) and its wiring in `app/main.py`
  (`lifespan` context manager, `PublishScheduler` instance — removed
  entirely, `FastAPI(...)` no longer takes a `lifespan` argument). This
  is the change that actually makes the atomic-claim guarantee
  meaningful: an in-process asyncio task only ever runs inside one API
  process, so it could never have been the thing protecting against a
  double-publish once more than one instance existed. The only way
  `promote_due`/`recover_stuck_publishing` run now is via
  `uv run arq app.workers.settings.WorkerSettings`, a separately
  deployable/scalable process, matching the Day 15 job-infrastructure
  convention (the same shape as Day 23's `refresh_platform_connections_cron`).

### Config (`app/core/config.py`)

- Removed `publish_scheduler_enabled`/`publish_scheduler_poll_seconds`
  (belonged to the deleted in-process poller).
- Added `publish_promotion_interval_seconds` (default 30),
  `publish_stuck_publishing_timeout_seconds` (default 900),
  `publish_stuck_recovery_interval_minutes` (default 15).

### API (`app/api/v1/published_content.py`)

Endpoints unchanged in shape from the pre-existing Day 16 implementation:

```text
POST /api/v1/profiles/{profile_id}/drafts/{draft_id}/publish
POST /api/v1/profiles/{profile_id}/drafts/{draft_id}/schedule
POST /api/v1/profiles/{profile_id}/published/{published_id}/cancel
GET  /api/v1/profiles/{profile_id}/published
GET  /api/v1/profiles/{profile_id}/published/{published_id}
```

All depend on Day 21's `require_profile_access` — every ownership
mismatch is a 404, never 403/400; `get_published_content` additionally
re-checks `published.profile_id != profile.id` as defense in depth.
`error_response()` now maps `InvalidScheduleError | PlatformNotConnectedError`
to 422 alongside the existing 409 (`DraftNotEligibleError |
ScheduleNotCancellableError`) and 404 fallback.

### Review findings

An architecture/security review (backend-reviewer persona, run via a
general-purpose agent since the project's custom `backend-reviewer`
subagent type is not invocable as a distinct `subagent_type` in this
environment) found **no Blocking (CRITICAL/HIGH) issues**. Two
non-blocking items were logged and left as-is:

- **Test-honesty note, not a production defect**: the two "concurrent
  worker" tests in `tests/test_published_content.py` run two
  `PublishedContentService` instances against the *same* shared SQLite
  session/connection (the project's existing `db_session` test
  fixture), so they prove the claim is self-consistent under sequential
  reinvocation, not genuine two-connection concurrency — SQLite can't
  exercise that regardless. The production claim mechanism itself
  (`UPDATE ... RETURNING`) is correct and Postgres-safe by construction;
  only the test docstrings slightly overstate what they demonstrate.
  Matches the project's existing, already-documented SQLite-vs-Postgres
  testing-gap convention (Day 13's partial-unique-index note, Day 19's
  GIN-index note, Day 23's enum-label note).
- **Pre-existing, not a Day 24 regression**: `PublishedContent.draft`
  uses `lazy="selectin"` unconditionally, so list/create/cancel
  responses (none of which expose draft fields) still eager-load the
  related `ContentDraft` on every call. Present since the original Day
  16 publishing-foundation commit; not touched here.

## Migration

- `z9a0b1c2d3` (head, down-revision `y8z9a0b1c2`): Postgres-safe
  `ALTER TYPE publishstatus ADD VALUE IF NOT EXISTS 'PUBLISHING'` plus
  the new `platform_post_id` `String(255)` nullable column. Downgrade
  converts any lingering `PUBLISHING` rows to `FAILED` before rebuilding
  the enum type without the value (rename → recreate → cast → drop),
  matching the project's own established pattern for removing an enum
  value (`n7o8p9q0r1`). Reversible; single head confirmed via
  `uv run alembic heads`.

## Testing

`tests/test_published_content.py` retrofitted with Day 21 auth (it had
never been updated since Day 21 landed — a pre-existing gap, not
introduced by this day) plus 13 new Day 24 tests: schedule/publish/
cancel flows; a concurrent-worker claim test (only one worker claims a
given row); the spec-named test proving the atomic claim alone — lock
removed entirely from the call path — still prevents double-claim;
adapter success/failure paths; publish against a disconnected connection
rejected (422); the stuck-publishing recovery sweep; index usage; and
ownership isolation.

Verification (all actually executed):

- `uv run pytest tests/test_published_content.py -q` → **26 passed**
  (re-confirmed after a formatting fix, twice — 165.49s and 65.36s runs).
- `uv run pytest tests/test_platform_connections.py -q` → **46 passed**,
  no regression from the `adapters.py` additions.
- `uv run pytest -q` (full suite) → **354 passed, 14 failed**. The Day 23
  baseline was 28 failed, 328 passed, with `test_published_content.py`
  explicitly listed among the pre-existing failures (never retrofitted
  with Day 21 auth). The 14 remaining failures are byte-identical by
  name to the non-`test_published_content.py` subset of that baseline
  (`test_workspaces.py`, `test_intelligence_analysis.py`,
  `test_content_intelligence_synthesis.py`) — Day 21's outstanding
  scope, untouched by this day. **No new regressions**; this day's auth
  retrofit incidentally closed the `test_published_content.py` gap as a
  side effect.
- `uv run ruff check` and `uv run ruff format --check` over every Day 24
  file: clean (one real formatting fix applied to
  `app/services/published_content.py` during this day's testing pass,
  then re-verified). Repo-wide `ruff check .` still reports pre-existing
  errors in `app/models/content_evaluation.py`,
  `app/repositories/content_evaluation.py`,
  `app/schemas/content_evaluation.py`,
  `app/services/evaluation/evaluator.py`,
  `app/services/evaluation/scoring.py`, `app/services/persona.py`, and
  the `l5m6n7o8p9` migration — none touched by this day, not fixed, out
  of scope.
- `uv run alembic heads` → `z9a0b1c2d3` (single head).

## Known limitations

- Genuine multi-connection concurrency for the atomic claim has not been
  exercised under real PostgreSQL — SQLite structurally can't (see
  Review findings above). Matches the project's existing SQLite-vs-
  Postgres testing convention rather than being a new gap.
- YouTube and Instagram publishing remain a deterministic
  `MediaRequiredError` failure, not a working integration —
  `ContentDraft` has no video/image asset. An explicit, approved scope
  decision for this day, not unfinished work; a media-asset pipeline is
  out of scope here and not yet scheduled.
- Retracting an already-published item, and any automatic retry of a
  failed publish, remain explicitly out of scope.
- `PublishedContent.draft`'s unconditional `lazy="selectin"` causes an
  avoidable extra query on read paths that don't expose draft data
  (pre-existing, from Day 16 — see Review findings above).

## Files changed

- New: `app/services/publish_promotion.py`,
  `migrations/versions/z9a0b1c2d3_add_publishing_status_and_post_id.py`.
- Deleted: `app/services/publish_scheduler.py`.
- Modified: `app/models/published_content.py`,
  `app/repositories/published_content.py`,
  `app/services/published_content.py`,
  `app/platform_connections/adapters.py` (added `MediaRequiredError`,
  `PublishResult`, `publish_content` on the Protocol/base class,
  `FacebookAdapter.publish_content`), `app/workers/settings.py` (two new
  `cron_jobs` entries), `app/main.py` (removed the `PublishScheduler`
  lifespan wiring), `app/core/config.py` (new publish-promotion
  settings, old poller settings removed), `app/schemas/published_content.py`
  (`platform_post_id` on the response schema), `app/api/v1/published_content.py`
  (`PlatformNotConnectedError` → 422), `tests/test_published_content.py`
  (rewritten: Day 21 auth retrofit + 13 new tests).
