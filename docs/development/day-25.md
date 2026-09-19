# Day 25 - Performance Ingestion Pipeline

## Objective

Attach recorded metrics to a specific `PublishedContent` record and
trigger the existing Day 9 `PerformanceAnalysis` logic against real,
lineage-connected data, running the analysis as an async job rather than
inline in the request.

Full architectural context: `docs/product/product-architecture.md`
("Performance Intelligence," "AI Execution and Job Control" — long-running
work belongs in background jobs, not inline in request handling) and
`docs/development/progress.md` (Day 9 `ContentPerformance` /
`PerformanceAnalysis` / `PerformanceInsight` foundation, Day 15 job
infrastructure, Day 21 ownership-chain enforcement, Day 24
`PublishedContent`).

### Numbering note

`ContentPerformance`, `PerformanceAnalysis`, and `PerformanceInsight`
already existed before this day began (Day 9) — profile-scoped only, with
no link to a specific `PublishedContent` record, and analysis triggered
synchronously. This day connects that existing pipeline to real published
lineage and converts its trigger path to the Day 15 async job queue; it
does not change the Day 9 scoring/classification formulas themselves.

## Scope

In scope:

- `published_content_id` FK on `ContentPerformance`, nullable (pre-Day-25
  profile-scoped records never had one; the new endpoint always sets it).
- Manual metrics-entry endpoint accepting
  views/likes/comments/shares/saves/reach/watch_time/retention for a
  `published_content_id`. Enqueues an async job (Day 15 queue) that runs
  the existing Day 9 `PerformanceAnalysis` logic against the submitted
  data. The endpoint returns a job reference immediately — it does not run
  analysis inline.
- Ownership validation: metrics can only be attached to `PublishedContent`
  the caller owns via the workspace/profile chain.

Explicitly out of scope this day:

- Live polling of social platform APIs — metrics remain caller-submitted,
  matching Day 9's original "no external OAuth flow or social API
  integration" boundary for this domain.
- Learning Engine (Day 26) — `PerformanceInsight` feeding back into
  `ContentOpportunity` scoring/strategy remains unimplemented.
- Any change to Day 9's scoring/classification formulas.

Architecture constraints:

- Router → Service → Repository layering, matching every other domain.
- Analysis must run through the Day 15 `arq` job queue, never inline in
  the request handler.
- AI-reasoned insight generation stays behind the Day 16
  `PerformanceInsightService`/`AIRouter` path; the deterministic
  `PerformanceAnalysis` must survive even if AI enrichment fails.

Security: ownership via Day 21's `require_profile_access(profile_id)`,
plus a profile-scoped `PublishedContentRepository.get_by_id` lookup for
the target `published_content_id` — any mismatch at either level is a
404, never 403/400.

## Implementation

### `ContentPerformance` model (`app/models/content_performance.py`)

- Added `published_content_id` (`ForeignKey("published_content.id",
  ondelete="CASCADE")`, nullable) and `reporting_period` (`Date`,
  nullable) — the period a metrics snapshot reports on.
- `UniqueConstraint("published_content_id", "reporting_period")` enforces
  duplicate-period rejection at the database level, not an
  application-level pre-check, so a genuine concurrent double-submission
  for the same published item/period can't race past a check-then-insert
  gap. NULL `published_content_id` values (pre-Day-25 profile-scoped
  records) never collide under it in either SQLite or PostgreSQL.
- `Index("profile_id", "published_content_id")` supports the
  baseline-comparison join as history grows.
- `published_content: Mapped["PublishedContent | None"]` relationship
  (`lazy="selectin"`).

### Service (`app/services/content_performance.py`)

- `submit_metrics(profile_id, workspace_id, published_content_id,
  arq_pool, reporting_period, **metrics)`: validates the profile, then
  looks up the `PublishedContent` scoped to that `profile_id` (404 via
  `ValueError` if missing or owned by a different profile). Inserts the
  `ContentPerformance` row and flushes; an `IntegrityError` from the
  unique constraint is caught and re-raised as
  `DuplicateReportingPeriodError` (mapped to `409` at the router). On
  success, enqueues the `performance_analysis` job via `submit_job` and
  commits once.
- `enqueue_analysis(profile_id, workspace_id, record_id, arq_pool)`: the
  pre-existing manual `/analyze` trigger, converted from an inline call
  into the same `submit_job` path — unifying both entry points (new
  metrics submission and the existing manual trigger) onto one
  asynchronous invocation pattern.
- `analyze()` (the Day 9 baseline-comparison/classification logic) is
  unchanged; only how it gets invoked changes.
- `_run_performance_analysis_job(payload)`: the job handler, registered
  against `PERFORMANCE_ANALYSIS_TASK = "performance_analysis"` via
  `register_handler` at module import time. Calls
  `PerformanceInsightService.create()`, which runs the unchanged Day 9
  `analyze()` first (and commits it) before attempting the Day 16
  AI-reasoned `PerformanceInsight`. Per the "deterministic first, AI
  enriched" rule, an `AIError` (all providers unavailable) does not fail
  the job or lose the analysis — the deterministic `PerformanceAnalysis`
  already committed survives regardless of insight generation's outcome.

### API (`app/api/v1/performance.py`)

```text
POST /api/v1/profiles/{profile_id}/published/{published_id}/metrics
POST /api/v1/profiles/{profile_id}/performance/{performance_id}/analyze
```

Both return `202 ACCEPTED` with a job reference
(`content_performance_id`/`job_id`/`job_status`) immediately; neither runs
analysis inline. `submit_metrics` additionally maps
`DuplicateReportingPeriodError` to `409 CONFLICT`. Pre-existing CRUD
endpoints (`create`/`list`/`get`/`update`/`delete`) and the insight
endpoints are unchanged in shape.

### Worker wiring (`app/workers/settings.py`)

`app.services.content_performance` is imported at worker-module scope
(`# noqa: F401`) purely for its import side effect of calling
`register_handler` — the worker process never imports the API router, so
this import is what makes `performance_analysis` resolvable via
`get_handler()` when a job of that `task_type` is dequeued.

## Migration

- `b7c8d9e0f1a2` (head, down-revision `z9a0b1c2d3`): adds
  `published_content_id`, `reporting_period`, the FK, the unique
  constraint, and both indexes; fully reversible. Originally authored as
  `a1b2c3d4e5f6`, which collided with the pre-existing
  `a1b2c3d4e5f6_create_business_domain.py` revision id — renamed to
  `b7c8d9e0f1a2` so `uv run alembic heads` resolves to a single head
  instead of erroring on a duplicate revision.

## Testing

`tests/test_performance.py`: 7 tests total — the pre-existing Day 9
CRUD/median-analysis and workspace-isolation coverage, plus five new Day
25 tests:

- ownership rejection (404) for a `published_content_id` the caller
  doesn't own;
- successful submission enqueueing a job;
- duplicate-period submission resolving to `409 CONFLICT`;
- a genuine concurrent duplicate-period race resolving to exactly one
  success — via a new `db_session_factory` test fixture backed by a
  `StaticPool`-shared SQLite in-memory engine, since the project's default
  single-session fixture can't exercise a real two-connection race;
- baseline comparison against real `PublishedContent` history.

`tests/conftest.py` and the `create_opportunity` helper in
`tests/test_content_briefs.py` (shared by the concurrency test's
fixtures) were adjusted in support of this: the former adds the shared
session-factory fixture, the latter reuses an existing
`MarketIntelligence` record instead of creating a duplicate one per call,
fixing a pre-existing test-isolation bug the new test path exposed.

Verification (all actually executed):

- `uv run pytest tests/test_performance.py -v` → **7 passed**.
- `uv run pytest -q` (full suite) → **359 passed, 14 failed**, byte-identical
  by name to the pre-existing baseline documented in Day 24's entry
  (`test_workspaces.py`, `test_intelligence_analysis.py`,
  `test_content_intelligence_synthesis.py` — Day 21's outstanding scope).
  No new regressions.
- `uv run ruff check` / `uv run ruff format --check` over every Day 25
  file (model, service, schema, router, migration, the three test files):
  clean. Repo-wide `ruff check .` still reports the same pre-existing,
  untouched errors noted in Day 24's entry plus similar drift in
  `app/services/persona.py` and the `l5m6n7o8p9` migration — none touched
  by this day.
- `uv run alembic heads` → `b7c8d9e0f1a2` (single head), after the
  revision-id rename above.
- `uv run alembic check` could not be run against a live PostgreSQL
  instance in this environment (no reachable Postgres server) — matches
  the project's existing SQLite-vs-Postgres testing-gap convention. The
  migration was instead verified by direct read-through against the
  model's column/constraint/index definitions.

## Known limitations

- Metrics entry remains manual/caller-submitted; there is no live polling
  or scheduled pull from platform APIs, matching Day 9's original scope
  boundary and this day's explicit out-of-scope list.
- The unique-constraint concurrency test exercises a real SQLite
  `StaticPool`-shared two-session race rather than genuine PostgreSQL
  multi-connection concurrency — a real-Postgres verification has not
  been performed, matching the project's existing SQLite-vs-Postgres
  testing convention (Day 13/19/23/24's own notes) rather than being a
  new gap.
- `PerformanceInsight` generation from the async job path depends on the
  same AI provider availability as the pre-existing Day 16 insight flow;
  no new fallback behavior was added beyond the existing
  deterministic-first guarantee.
- `PerformanceInsight` does not yet feed back into `ContentOpportunity`
  scoring or strategic synthesis beyond the existing Day 17
  synthesis-invalidation hook — closing that loop is Day 26 (Learning
  Engine), not this day.

## Files changed

- Modified: `app/models/content_performance.py` (`published_content_id`,
  `reporting_period`, unique constraint, index, relationship),
  `app/services/content_performance.py` (`submit_metrics`,
  `enqueue_analysis`, `DuplicateReportingPeriodError`, the
  `performance_analysis` job handler and its registration),
  `app/schemas/content_performance.py`
  (`PerformanceMetricsEntryCreate`/`Response`,
  `PerformanceAnalysisPendingResponse`, `published_content_id`/
  `reporting_period` on the response schema), `app/api/v1/performance.py`
  (`submit_metrics` and `analyze` endpoints), `tests/conftest.py`
  (`db_session_factory` fixture), `tests/test_performance.py` (five new
  tests), `tests/test_content_briefs.py` (`create_opportunity` fixture
  fix).
- New: `migrations/versions/b7c8d9e0f1a2_add_performance_ingestion_pipeline.py`.
