# AI Content Studio Development Progress

## Current Status

Days 1 through 17 establish the first complete strategic content loop:

```text
Understand
  -> Decide
  -> Brief
  -> Create
  -> Evaluate
  -> Publish (manual confirmation)
  -> Measure / Learn (foundation established)
```

The backend is a FastAPI modular monolith using SQLAlchemy, Alembic, Pydantic,
PostgreSQL conventions, `uv`, pytest, and Ruff. Tests use an in-memory SQLite
database through the shared test fixtures.

The product is intentionally strategy-first. Signals do not directly generate
content. The implemented architecture evaluates profile context, audience
context, goals, and performance intelligence before content reaches the brief
and creation stages.

## Day 1 - Backend Foundation and Health

Established the Python/FastAPI backend structure and the first operational
conventions:

- FastAPI application entry point and versioned API routing.
- Async SQLAlchemy database setup and shared dependency injection.
- Alembic migration configuration and migration environment.
- Central configuration and structured request logging.
- Health endpoint for basic service verification.
- pytest fixtures with an isolated SQLite database for fast API tests.
- Initial router, service, repository, schema, and model layering.

The key outcome was a working backend foundation that could grow as a modular
monolith without coupling HTTP handlers directly to persistence logic.

## Day 2 - Workspace and Universal Content Profile

Added the multi-tenant root of the product:

- `Workspace` as the tenant boundary.
- `WorkspaceMember` with owner, admin, and member roles.
- `ContentProfile` as the universal strategic root.
- Support for creator and business profiles, with the architecture prepared
  for personal brands, experts, coaches, startups, local businesses, and
  ecommerce brands.
- UUID identifiers, timezone-aware timestamps, and JSON metadata conventions.
- Workspace-scoped profile CRUD APIs and ownership validation.

This established the central product decision that creators and businesses use
one Content Intelligence and Content Strategy architecture. The system does
not fork into separate creator and business strategy engines.

## Day 3 - Brand Intelligence and Optional Business Context

Added the first intelligence and commercial extension domains:

### Brand Intelligence

- Brand positioning, mission, vision, USP, voice, tone, and visual identity.
- Brand service, repository, schemas, API routes, and tests.
- Brand information attached to the universal ContentProfile.

### Business Context

- Optional `BusinessContext` extension for commercial profiles.
- Products with features, benefits, and target-audience metadata.
- Services with the corresponding service-level information.
- Offers with terms, active state, and date boundaries.
- CRUD services and APIs for business context, products, services, and offers.

BusinessContext is deliberately optional. A creator can use the platform
without products, services, offers, or commercial objectives.

## Day 4 - Audience Intelligence

Built the unified audience understanding domain:

- `AudienceIntelligence` for summary, language, geography, demographics,
  psychographics, behavior, and content preferences.
- Personas with goals, pain points, desires, behaviors, and preferences.
- Pain points with severity and frequency.
- Desires with importance.
- Audience questions with context, frequency, and importance.
- Audience objections with descriptions and refutations.
- Services, repositories, schemas, hierarchical APIs, and tests for each
  audience resource.

All audience resources are profile-scoped and available to creators and
businesses through the same architecture.

## Day 5 - Market Intelligence

Added the market understanding domain:

- `MarketIntelligence` for market summary and context.
- Topics with descriptions and relevance scores.
- Market signals with source information, signal type, velocity,
  engagement, and relevance scores.
- Competitors with positioning, strengths, weaknesses, and differentiation.
- CRUD services, repositories, schemas, APIs, and tests.

Market signals are intelligence inputs. They are not automatic content
generation triggers.

## Day 6 - Strategic Opportunity Foundation and Audience Signals

Established the first strategic decision layer between intelligence and
content execution:

- `AudienceSignal` for audience questions and related content needs.
- Signal intent values such as learn, compare, solve, discover, validate, and
  entertain.
- Signal lifecycle values such as active, resolved, expired, and archived.
- Manual signal ingestion as the initial source, with an extensible design.
- `ContentOpportunity` linked to a profile and, when applicable, market,
  audience, or performance sources.
- Opportunity sources including trend, performance gap, audience question,
  pillar rotation, and market conversation.
- Target objectives: growth, authority, lead generation, and sales.
- Opportunity priority and lifecycle statuses.
- Relevance and opportunity scores with strategic metadata.

The opportunity layer enforces the product rule:

```text
Signal + Profile Context + Audience + Goals + Performance
  -> ContentOpportunity
```

It does not collapse raw intelligence into content.

## Day 7 - Content Opportunity Engine

Implemented the first deterministic opportunity evaluation flow:

- Opportunity creation from structured market and audience signals.
- Profile and workspace ownership validation before evaluation.
- Shared opportunity model for creators and businesses.
- Optional BusinessContext support without making commercial data mandatory.
- Deterministic scoring through `app/ai/strategy/opportunity_scorer.py`.
- Scoring inputs include signal strength, goal alignment, and timeliness.
- Priority mapping from score to high, medium, or low.
- Opportunity lifecycle and strategic rationale persistence.
- Hierarchical opportunity APIs and test coverage.

The output is a strategic reason to create content, not a caption, hook, draft,
or raw trend record.

## Day 8 - Audience Signals as First-Class Strategy Inputs

Expanded the opportunity engine beyond market trends:

- Audience questions became first-class strategic inputs.
- Audience signals can be converted into evaluated content opportunities.
- Audience signal ownership is validated through the profile and workspace.
- Creator workflows work without BusinessContext, products, services, or
  offers.
- Audience signal and opportunity APIs support creation, retrieval, listing,
  update, filtering, and ownership failure paths.

The strategic flow is now:

```text
Audience Question + Profile Context + Goals
  -> ContentOpportunity
```

The system still does not generate content directly from a question.

## Day 9 - Performance Intelligence v1

Added the first performance intelligence and learning foundation:

- `ContentPerformance` for normalized content performance data.
- `PerformanceAnalysis` for deterministic metric and baseline analysis.
- `PerformanceInsight` for structured explanations of what worked or failed.
- Metrics such as views, likes, comments, shares, saves, reach, watch time,
  retention, and engagement rates.
- Historical baseline comparisons for a profile.
- Winning and underperforming pattern identification.
- Structured performance reasoning through the AI layer with deterministic
  analysis as the evidence base.
- Performance gaps as valid ContentOpportunity sources.
- Social platform adapter contracts for future Facebook, Instagram, TikTok,
  YouTube, LinkedIn, and X integrations.
- Normalization boundaries so internal intelligence does not depend on any
  platform's response format.

No external OAuth flow or social API integration was added. The architecture
is prepared for adapters without coupling the core domain to a provider.

## Day 10 - Provider-Agnostic AI Infrastructure

Established the reusable AI execution layer:

- `AITask` describes what the application needs.
- AI capabilities describe what a provider or model can do.
- `AIProvider` is the provider abstraction rather than an LLM-specific type.
- `AIRouter` selects providers and models using task policy and capability
  requirements.
- Structured generation requests and validated Pydantic response models.
- Provider/model metadata including provider, model, and latency.
- Gemini integration behind the provider boundary.
- Explicit task policy for current MVP tasks such as research, strategy,
  opportunity analysis, content concepts, and performance reasoning.
- Failure handling that allows domain services to preserve deterministic
  results when AI is unavailable.

Product and strategy services do not import provider SDKs directly. AI remains
an execution and reasoning layer inside the larger strategy system.

## Day 11 - Content Brief Engine

Added the strategic contract between opportunity and creation:

- `ContentBrief` linked to exactly one ContentOpportunity and one profile.
- Brief title, core message, angle, big idea, and strategic rationale.
- Target objective, persona, pain point, desire, and audience question links.
- Recommended platform, format, and length.
- Tone, voice guidelines, CTA strategy, key points, supporting context, and
  success criteria.
- Brief version, generation source, status, and metadata.
- Deterministic brief composition from the opportunity and available
  intelligence.
- Optional AI enrichment through the AI Router.
- Safe fallback to the deterministic brief if enrichment fails.
- Brief lifecycle and CRUD APIs.
- Full profile, opportunity, workspace, and optional intelligence ownership
  validation.

The brief is intentionally not final creative copy. It is the strategic
instruction that constrains future creation.

## Day 12 - Content Creation Engine v1

Implemented the first execution layer:

- `ContentDraft` linked to its profile and source ContentBrief.
- Draft fields for platform, format, title, hook, body, caption, and CTA.
- Draft lifecycle: draft, ready, approved, and archived.
- Server-controlled generation sources: deterministic, AI, AI fallback, and
  manual.
- Composition modes for composed and manually supplied content.
- Deterministic content creation from the brief.
- AI-assisted content creation through `AIRouter` and Gemini.
- Automatic deterministic fallback when AI generation fails.
- Provider, model, prompt version, and lineage metadata.
- Draft CRUD APIs and profile/workspace isolation.
- Strategic lineage from draft back to brief, opportunity, and intelligence.

Day 12 produces textual execution output. It does not publish, schedule, or
generate images, video, audio, or external platform assets.

## Day 13 - Multi-Variant Creative Generation

Extended a ContentDraft with constrained creative alternatives:

- `ContentDraftVariation` for hook and caption alternatives.
- One unified variation model instead of separate hook and caption tables.
- Variation indexes with uniqueness per draft and variation type.
- At most one selected hook and one selected caption per draft.
- PostgreSQL partial unique index for selected variations, with a SQLite
  equivalent for the test database.
- `variation_index >= 1` database check constraint.
- Deterministic and AI-assisted variation generation.
- New AI tasks and policy entries for hook and caption generation.
- Server-controlled generation metadata.
- Variation listing and selection APIs.
- Selection synchronization into `ContentDraft.hook` and
  `ContentDraft.caption`.
- Race-condition handling for concurrent uniqueness conflicts, returning a
  controlled conflict response instead of an unhandled database error.
- Explicit missing-draft, missing-variation, and cross-tenant ownership tests.

Variations change how the strategic idea is expressed. They cannot change the
objective, audience, pillar, topic, strategic angle, emotion, success metrics,
or recommended format from the parent brief.

## Day 14 - Content Quality and Strategic Alignment Evaluation

Implemented evaluation of a draft, with an optional selected variation, against
its ContentBrief:

- `ContentEvaluation` stores a historical assessment for a draft.
- `ContentEvaluationFinding` stores dimension-level explanations and
  recommendations.
- Nine scored dimensions:
  - strategic alignment
  - audience relevance
  - hook strength
  - message clarity
  - narrative coherence
  - format alignment
  - emotional alignment
  - CTA alignment
  - brand alignment
- Scores are constrained to the `0.0` to `1.0` range.
- Overall score is calculated by the application using deterministic weights:

```text
strategic alignment  0.20
audience relevance   0.15
hook strength        0.15
message clarity      0.10
narrative coherence  0.10
format alignment     0.10
emotional alignment  0.05
CTA alignment        0.05
brand alignment      0.10
total                1.00
```

- Deterministic classification:
  - excellent: `>= 0.85`
  - strong: `>= 0.70`
  - acceptable: `>= 0.55`
  - weak: `>= 0.40`
  - poor: `< 0.40`
- Stage A deterministic heuristic evaluation always produces a usable result.
- Stage B optionally enriches findings and scores through the AI Router.
- AI failure preserves the deterministic evaluation and marks it as an
  AI fallback.
- Recommendations improve execution and cannot redefine strategy.
- Historical evaluations remain separate records rather than overwriting the
  previous assessment.
- Hierarchical create, list, and retrieve APIs were added.
- Workspace, profile, draft, and optional variation ownership is enforced with
  404 responses for inaccessible resources.
- Creator evaluation works without BusinessContext.
- The SQLAlchemy `metadata` reserved-name issue was handled by exposing the
  Python attribute as `evaluation_metadata` while retaining the database
  column name `metadata`.

## Day 15 - Scalable Platform Foundation

A pure infrastructure day: no product/domain feature was built. Everything
here is reusable plumbing for Days 16+ (see
`docs/development/day-15.md` for the full spec).

- New `app/infrastructure/` module (`jobs/`, `cache/`, `ratelimit/`,
  `locks/`), injected into domain services rather than imported ad hoc.
  Domain services never import Redis or an arq client directly.
- Background jobs: `AIJob` model / `ai_jobs` table (`id`, `task_type`,
  `profile_id`, `status` — `queued`/`running`/`succeeded`/`failed`/
  `timed_out` — `attempts`, `submitted_at`, `started_at`, `finished_at`,
  `error`, `result_ref`), indexed on `(profile_id, status)` and `(status,
  submitted_at)`. `app.infrastructure.jobs.service.submit_job` creates the
  row and enqueues an arq job in one call, using the row's id as arq's
  `_job_id`. The arq worker entrypoint `execute_ai_job`
  (`app/workers/settings.py`, run via
  `uv run arq app.workers.settings.WorkerSettings`, a process separate from
  the API) dispatches to a `task_type` → handler registry, enforces a
  per-job `asyncio.wait_for` timeout, and retries with exponential backoff
  (`base * 2^(attempt-1)`) up to a bounded attempt count before finalizing
  as `failed` or `timed_out`. No product task type is registered yet — only
  an `infrastructure.echo` placeholder handler exists for tests.
- `CacheService` (`get_or_compute`, `invalidate`, `invalidate_prefix`) wraps
  Redis with namespaced keys and SCAN-based (never blocking `KEYS`) prefix
  invalidation. Not wired into any real endpoint yet — later days use it.
- Redis-backed sliding-window rate limiting middleware, applied per
  best-effort user identifier and per workspace (see "Platform
  Infrastructure" below for why "per user" is a placeholder), with a lower
  default ceiling for a configurable set of AI-triggering route prefixes
  than for plain CRUD routes. Ships with `rate_limit_enabled` defaulting to
  `False` (see "Platform Infrastructure").
- Idempotency-Key dedup (`app.infrastructure.jobs.idempotency`) for
  job-submission endpoints: a Redis `SET NX EX` claim, scoped per operation,
  so a client retry within the TTL window is rejected rather than
  submitting a duplicate job. No job-submission endpoint exists yet to wire
  it into — it is reusable infrastructure for Days 17+.
- `DistributedLock` (`app/infrastructure/locks/service.py`) wraps redis-py's
  own `Lock` (`SET NX PX` plus a token-checked, safe release), defaulting to
  a single non-blocking acquisition attempt; a `try_lock` context manager
  yields whether it was acquired. Available for a future scheduler that
  needs to coordinate across more than one instance.
- Explicit, environment-driven SQLAlchemy async engine pool sizing
  (`db_pool_size`, `db_max_overflow`, `db_pool_timeout_seconds`) and a
  connection-level Postgres `statement_timeout`
  (`db_statement_timeout_ms`), applied only for the `postgresql` driver —
  SQLite (the test suite) is left on library defaults, which don't support
  either concept the same way.

See "Platform Infrastructure" below for the pool-sizing formula, cache key
conventions, and the rate-limit-default rationale, so later days can
reference it instead of re-explaining it.

## Day 16 - Content Library

Implemented a workspace-scoped retrieval layer over existing `ContentDraft`
records with filtering, pagination, sorting, and lineage retrieval:

- Added read-only library endpoints:
  - list drafts in a workspace with optional filters
  - retrieve a single draft with `ContentBrief` and `ContentOpportunity`
    lineage summary
- Added library filters for:
  - `profile_id`
  - `platform`
  - `format`
  - `status` (`draft`, `ready`, `approved`, `archived`)
  - created-at date range (`created_after`, `created_before`)
- Added simple full-text-like search over draft `title`, `hook`, and
  `caption` using SQL contains/ILIKE semantics.
- Preserved existing pagination and sorting conventions:
  - `skip` / `limit` pagination
  - sort by `created_at` or `updated_at` with `asc` / `desc`
- Implemented through Router -> Service -> Repository layering without adding
  a new domain model.
- Enforced workspace/profile ownership boundaries with 404 responses for
  inaccessible resources.
- Kept Content Library retrieval-only and separate from draft editing,
  publishing, and performance analytics concerns.

Day 16 intentionally reuses `ContentDraft` as the canonical content record.
No `LibraryContent` or duplicate content-item model was introduced.

## Day 17 - Publishing Foundation

Introduced the first publishing record, closing the "Publish" stage of the
core product loop with manual confirmation, scheduled publishing, and
schedule cancellation as the MVP mechanisms:

- `PublishedContent` model recording that a `ContentDraft` went live (or will):
  `draft_id`, `profile_id`, `platform`, `external_url` (nullable),
  `scheduled_at` (nullable), `published_at` (nullable until actually
  published), `publish_method` (`manual` implemented; `api` reserved for a
  future real integration), `status` (`scheduled`, `published`, `failed`,
  `retracted`, `cancelled`), `created_at`. A composite index on
  `(status, scheduled_at)` backs the scheduler's due-row query.
- `PublishedContentService.publish_draft` and `.schedule_draft` both validate
  the full workspace/profile ownership chain and require the draft's status
  to be `ready` or `approved` (rejecting any other status with a `409
  Conflict`, distinct from the `404` ownership-chain failures), without
  mutating any of the draft's own strategic fields (hook, body, caption,
  status, brief link). `schedule_draft` additionally rejects a past
  `scheduled_at` with `422`.
- `PublishedContentService.cancel_schedule` moves a `scheduled` record to
  `cancelled` if it hasn't fired yet; cancelling anything else (already
  published, failed, retracted, or cancelled) returns `409`. Retracting an
  already-published item is intentionally out of scope.
- `PublishedContentService.promote_due` (backed by
  `PublishedContentRepository.claim_due`) is the operation an in-process
  `PublishScheduler` (`app/services/publish_scheduler.py`) calls on a
  configurable interval (default 30s), started/stopped via the FastAPI
  `lifespan`. It performs one atomic `UPDATE ... WHERE status = 'scheduled'
  ... RETURNING` to claim due rows before calling the adapter, so the same
  row can never be double-processed even if more than one app instance ran
  the poller. This is a narrow, single-purpose poller, not a general job
  queue — no arq/Redis, no persisted job records.
- Extended the Day 9 `SocialPlatformAdapter` Protocol with a `publish(...)`
  method and added a `ManualPlatformAdapter` no-op implementation — reusing the
  existing adapter contract rather than introducing a new one, shared by both
  the immediate-publish and scheduled-promotion code paths. No OAuth flow or
  real Facebook/Instagram/TikTok/etc. API call was implemented.
- API: `POST /profiles/{profile_id}/drafts/{draft_id}/publish`,
  `POST /profiles/{profile_id}/drafts/{draft_id}/schedule`,
  `POST /profiles/{profile_id}/published/{published_id}/cancel`,
  `GET /profiles/{profile_id}/published` (filterable by `platform` and
  `status`, paginated), and `GET /profiles/{profile_id}/published/{published_id}`
  returning full lineage back through draft -> brief -> opportunity.
- Alembic migrations add the `published_content` table (FKs to
  `content_drafts` and `content_profiles`, both `CASCADE`) and a follow-up
  migration adding the `scheduled`/`cancelled` statuses, the `scheduled_at`
  column, and the composite index.
- Workspace/profile ownership enforced identically to draft endpoints, with
  404 for any ownership-chain mismatch.

Day 17 intentionally does not implement a general job/task queue, retry-on-
failure logic for the (still manual/no-op) platform publish call, retracting
an already-published item, or performance metrics ingestion — performance
ingestion from published content is Day 18.

## Architecture After Day 17

```text
Workspace
  |
  +-- ContentProfile
        |
        +-- Brand Intelligence
        +-- Audience Intelligence
        |     +-- Personas
        |     +-- Pain Points
        |     +-- Desires
        |     +-- Audience Questions
        |     +-- Audience Signals
        +-- Market Intelligence
        |     +-- Topics
        |     +-- Market Signals
        |     +-- Competitors
        +-- Performance Intelligence
        |     +-- Content Performance
        |     +-- Performance Analysis
        |     +-- Performance Insights
        +-- Content Opportunities
              |
              +-- Content Briefs
                    |
                    +-- Content Drafts
                          |
                          +-- Draft Variations
                          +-- Content Evaluations
                          |     +-- Evaluation Findings
                          +-- Published Content
```

The request flow remains:

```text
Router
  -> Service
    -> Repository
      -> SQLAlchemy
        -> Database
```

Routers handle HTTP concerns, services own business rules and ownership
validation, and repositories handle persistence and queries.

Alongside this domain tree, Day 15 added `ai_jobs` as a parallel
infrastructure table (FK to `ContentProfile.id`, but not part of the
Intelligence/Strategy/Creation tree above) and the `app/infrastructure/`
module described below.

## Platform Infrastructure

Reference material for Days 16+ so they can build on this instead of
re-explaining it. Full spec: `docs/development/day-15.md`.

### Job queue

- **Library**: `arq` (already a project dependency prior to Day 15), chosen
  over Celery because the codebase is async-native end to end (FastAPI +
  SQLAlchemy async) and had no prior Celery conventions to preserve.
- **Worker entrypoint**: `uv run arq app.workers.settings.WorkerSettings`,
  a process separate from `uvicorn app.main:app`.
- **Status table**: `ai_jobs` — see the Day 15 summary above for columns
  and indexes.
- **Retry/backoff**: bounded by `job_max_attempts` (default 3); backoff is
  `job_retry_backoff_base_seconds * 2^(attempt-1)` (default base 2s, so
  2s / 4s / 8s between attempts). Per-job execution timeout is
  `job_timeout_seconds` (default 30s), enforced with `asyncio.wait_for`
  around the dispatched handler.
- **Handler registration**: `app.infrastructure.jobs.registry.
  register_handler(task_type, handler)`. No product task type is
  registered as of Day 15.

### Database connection pool sizing

Environment-driven settings (`db_pool_size`, `db_max_overflow`,
`db_pool_timeout_seconds`, `db_statement_timeout_ms`), applied only when
`database_url` is a `postgresql` URL (SQLite, used by the test suite,
doesn't support the same pool/timeout semantics and is left on defaults).

Sizing formula:

```text
(app instances) x (db_pool_size + db_max_overflow) <= postgres max_connections - headroom
```

Current defaults — `db_pool_size=10`, `db_max_overflow=5` — are sized for a
small number of app instances against a default-ish managed Postgres
`max_connections` (100), leaving headroom for the migration runner, the
separate worker process(es), and manual/admin connections:

```text
instances x (10 + 5) <= 100 - headroom
```

At `headroom ~= 25`, that supports up to 5 app instances
(5 x 15 = 75 <= 75). Re-derive this per deployment tier against that
tier's actual `max_connections` rather than assuming these defaults —
they are a starting point, not a validated production value.

Statement timeout: `db_statement_timeout_ms` (default 30000ms), set via
asyncpg `connect_args={"server_settings": {"statement_timeout": "..."}}`
at connection time.

### Cache key conventions

`CacheService` (not wired into any endpoint yet) uses colon-separated,
namespaced keys scoped to the entity they describe:

```text
profile:{profile_id}:<facet>          e.g. profile:{id}:brand
profile:{profile_id}:<facet>:list     e.g. profile:{id}:opportunities:list
```

`invalidate_prefix("profile:{profile_id}:")` drops every cached read for
one profile in a single call via non-blocking `SCAN` (never `KEYS`).
Default TTL is `cache_default_ttl_seconds` (300s) unless a call site
passes its own.

### Rate limiting

Sliding-window counter (Redis sorted sets), applied per best-effort user
identifier (`X-User-Id` header, falling back to client address — there is
no real authenticated-user concept in this codebase yet) and per
`workspace_id` query parameter when a route carries one. Route
classification is by path-prefix substring match against
`ai_triggering_route_prefixes` (default: `/briefs`, `/drafts`,
`/variations`, `/evaluations`) — anything else is CRUD. Defaults:
`rate_limit_crud_requests_per_window=120`,
`rate_limit_ai_requests_per_window=20`, `rate_limit_window_seconds=60`.

**`rate_limit_enabled` defaults to `False`.** Flipping it on globally by
default would have made every existing test that drives the live `app`
over HTTP depend on a reachable Redis, none of which is available in this
development environment. Staging/production set it `true` via env var once
Redis is actually deployed there; the middleware, policy, and limiter are
fully implemented and covered by tests against a fake Redis client — only
the default is off pending a real Redis and real per-route tuning.

### Idempotency keys

`app.infrastructure.jobs.idempotency.claim_idempotency_key(redis, scope,
idempotency_key, ttl_seconds)` — a `SET NX EX` claim scoped per operation
name, `idempotency_key_ttl_seconds` default 600s. No job-submission
endpoint exists yet to call it from; it's ready for Days 17+.

### Distributed locks

`app.infrastructure.locks.service.DistributedLock` wraps redis-py's `Lock`
(`SET NX PX`, safe token-checked release), default a single non-blocking
acquisition attempt (`lock_default_timeout_seconds=30`). `try_lock(redis,
name)` is the non-blocking convenience wrapper. Not yet used by the Day 17
publish scheduler (which today is a single-poller, single-table design
that doesn't need cross-instance coordination) — available if a future
scheduler needs it.

## Cross-Cutting Guarantees

- Workspace isolation is checked through the full parent ownership chain.
- Cross-workspace and cross-profile access returns 404 rather than exposing
  resource existence.
- ContentProfile is the universal strategic root.
- BusinessContext is optional and never required by creator workflows.
- Server-controlled values such as IDs, ownership, scores, classifications,
  generation source, timestamps, and AI metadata cannot be claimed by clients.
- Strategic decisions remain separate from creative execution.
- AI is provider-agnostic and optional wherever a deterministic path exists.
- Database changes are represented through Alembic migrations.
- Domain entities use UUIDs and timezone-aware timestamps.
- Flexible metadata uses JSON/JSONB only where it provides lineage or
  extensibility value.

## Testing and Verification

The project contains focused tests for workspaces, profiles, brand, business
context, audience intelligence, market intelligence, opportunities,
performance, AI infrastructure, briefs, drafts, variations, evaluations, and
published content.

Day 13 was verified with:

- 174 tests passing for the complete suite at that point.
- Day 13 variation tests included in the regression run.
- Ruff checks clean for the Day 13 files.
- Ruff format checks clean for the Day 13 files.
- Migration chain validated with a single head.

Day 14 evaluation verification completed with:

- 22 evaluation tests passing.
- Scoring and classification unit tests passing.
- Deterministic evaluation endpoint passing.
- AI/fallback evaluation paths covered.
- Historical evaluation listing and retrieval passing.
- Creator support passing without BusinessContext.
- Cross-profile and cross-workspace isolation passing.
- Response field and finding structure tests passing.
- No editor diagnostics in the touched evaluation files.

Day 15 platform infrastructure verification completed with:

- 17 infrastructure tests passing: cache get/set/invalidate/invalidate_prefix
  (3), distributed lock acquire/release/contention/try_lock (3), Redis
  idempotency-key claim/scope-isolation (3), rate-limit sliding-window
  threshold/reset plus a live-middleware 429 test (2), job submission,
  success, forced-failure-then-retry-exhaustion, and timeout-then-terminal
  paths plus unknown-handler lookup (5), and simulated connection-pool
  exhaustion raising a bounded `TimeoutError` rather than hanging or
  crashing (1).
- Full 233-test repository regression suite passing in this verification
  run — no existing test was changed to accommodate Day 15; the global
  rate-limit middleware defaults to disabled specifically so it doesn't
  require every existing HTTP-driven test to reach a live Redis.
- Ruff checks and format checks clean for touched Day 15 files.
- Migration chain validated with a single head (`o8p9q0r1s2`).
- No real Redis, Postgres, or Docker daemon was available in this
  development environment; Redis-backed tests use `fakeredis` (with the
  `lupa` Lua backend, needed for redis-py's `Lock` safe-release script) and
  `AIJob` persistence uses the project's existing SQLite test-database
  convention. The arq worker function was exercised directly as a
  coroutine rather than through a live `arq.worker.Worker` loop against a
  real Redis, for the same reason — documented in `docs/development/day-15.md`
  rather than silently substituted.

Day 16 content library verification completed with:

- 6 content library tests passing.
- Filter, pagination, search, and lineage retrieval coverage passing.
- Cross-profile and cross-workspace isolation coverage passing.
- Full repository regression suite passing in this verification run.
- Ruff checks clean for touched Day 16 Python files.
- Repo-wide Ruff check still reports pre-existing unrelated violations outside
  Day 16 files.

Day 17 publishing verification completed with:

- 14 published content tests passing: publish success (`ready` and `approved`
  drafts), ineligible-status rejection, schedule creation, past-`scheduled_at`
  rejection, ineligible-draft scheduling rejection, `promote_due` promoting
  only due items, the atomic claim rejecting a second promotion attempt on an
  already-claimed row, cancel success and its exclusion from promotion,
  cancelling a non-scheduled item rejected, cancel ownership isolation, list
  filtering, lineage retrieval, and cross-workspace/cross-profile isolation on
  retrieval.
- Full repository regression suite passing in this verification run.
- Ruff checks and format checks clean for touched Day 17 Python files.
- Migration chain validated with a single head (`n7o8p9q0r1`).

## Known Limitations and Intentionally Deferred Work

The following are intentionally outside Days 1-17:

- Any product feature actually submitting a job through the Day 15 job
  queue — the infrastructure (arq worker, `ai_jobs` table, retry/backoff,
  timeout) exists, but no `task_type` handler is registered for a real AI
  task yet, and the Day 17 publish scheduler still deliberately remains its
  own narrow single-table poller rather than routing through the queue.
- `CacheService` wired into any real read path, and the rate limiter/
  idempotency-key helpers wired into any real endpoint (all built and
  tested in isolation per Day 15, `rate_limit_enabled` defaults `False`).
- Retry-on-failure logic for the actual platform publish call, and retracting
  an already-published item.
- Real OAuth flows and real Facebook, Instagram, TikTok, YouTube, LinkedIn, or
  X publishing API calls (`SocialPlatformAdapter.publish` remains a
  manual/no-op placeholder).
- Performance metrics ingestion from published content (Day 18).
- OAuth and external account connection flows.
- Image, video, audio, voice, and UGC generation.
- Full script generation and asset assembly.
- Remix and content transformation engines.
- Autonomous agents and multi-agent orchestration.
- RAG, embeddings, and vector databases.
- Microservices or distributed event infrastructure.
- New AI providers beyond the current provider abstraction and Gemini path.
- Trend detection and autonomous market research.
- A generic analytics dashboard.
- A real authenticated-user identity layer (the Day 15 rate limiter's
  "per user" bucket is a header/client-address placeholder, not
  authorization — see docs/product/product-architecture.md "Identity,
  Tenancy, and Authorization").

Known repository-level quality notes:

- Some pre-existing repo-wide lint and formatting drift remains outside the
  files changed for the development days.
- Tests use SQLite by project convention; a live PostgreSQL integration run has
  not been performed for the partial unique index and PostgreSQL-specific JSONB
  behavior.
- Some existing relationship loading patterns may perform an avoidable extra
  query at the current scale.
- Some existing endpoints classify certain errors by `ValueError` message,
  matching the established project convention rather than using dedicated
  exception types.
- Day 15's Redis-backed infrastructure is tested against `fakeredis`, and
  the arq worker function is tested as a directly-invoked coroutine rather
  than through a live `arq.worker.Worker` loop — no real Redis instance or
  Docker daemon was available in this development environment. A real-Redis
  integration pass (and a real arq worker end-to-end run) has not been
  performed, mirroring the project's existing SQLite-vs-Postgres testing
  convention rather than a new gap.

## Scope Confirmation

Days 1-17 implement the strategic foundation, intelligence inputs, opportunity
evaluation, brief composition, deterministic and AI-assisted draft creation,
creative variations, quality evaluation, workspace-scoped content library
retrieval, manual/scheduled publish confirmation with cancellation, and (Day
15) reusable platform infrastructure — background jobs, caching, rate
limiting, idempotency, distributed locks, and sized connection pooling — with
no product feature yet consuming it. No real social platform API
integrations, OAuth flows, advanced media generation, autonomous strategy
features, or real authenticated-user identity were added.
