# AI Content Studio Development Progress

## Current Status

Days 1 through 19, plus Day 16's Intelligence Reasoning Layer (see its
numbering note below), establish the first complete strategic content loop
and give Brand, Audience, and Market Intelligence their first LLM
reasoning layer. Day 18 gives the Opportunity Engine's `strategic_rationale`
its first LLM reasoning layer as well, grounded in the Day 17 cross-domain
synthesis. Day 19 upgrades the Day 16 Content Library retrieval layer to a
production-grade one: cursor-based pagination, Postgres full-text search,
and its first real read-through cache. Day 20 adds the system's first real
authentication layer — JWT login/refresh/logout, Redis-based revocation,
and password reset — and points the Day 15 rate limiter at real
authenticated identity instead of a client-supplied header:

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


## Day 17 (Content Intelligence Synthesis Engine) - Cross-Domain Strategic Synthesis

> **Numbering note:** This entry is also numbered "Day 17," duplicating the
> Publishing Foundation entry above, following the same established practice
> as the two "Day 16" sections earlier in this document. This entry keeps the
> Day 17 label pending a later renumbering pass by the project owner. Full
> spec, file-by-file detail, and the Definition of Done checklist live in
> `docs/development/day-17.md` (Section 7) — this entry is a summary only.

Implemented `strategic_synthesis`: the first module (`app/content_intelligence/`)
that reads across all four Content Intelligence domains at once — Brand,
Audience, and Market analysis (Day 16) plus Performance insights (Day 9) —
and combines whichever currently exist for a profile into one grounded
`ContentIntelligenceSynthesis` row, the first real implementation of the
architecture's "Content Intelligence is the Central Brain" principle.

Key points:

- Fewer than two available component domains (an `insufficient_data`
  component analysis doesn't count as available), or an AI provider failure,
  produces `generation_source=insufficient_data`/`ai_fallback` rather than a
  fabricated synthesis; `supporting_analyses` is always the
  deterministically-collected list of real component-analysis/insight ids,
  never anything the LLM returns.
- Any component regenerating (`intelligence_analysis.generate()` for Brand/
  Audience/Market, `PerformanceInsightService.create()` for Performance)
  flips `is_stale=True` and drops the cache entry, without eagerly
  regenerating — synthesis regenerates lazily on the next `GET`, avoiding a
  thundering herd when several components change close together.
- Runs through the Day 15 `ai_jobs` queue like the Day 16 domain tasks;
  `GET /api/v1/profiles/{profile_id}/synthesis` follows the same
  enqueue-or-serve, workspace-namespaced-cache pattern as Day 16, with a
  longer TTL (1800s vs. 300s) since this is the most expensive reasoning
  call in the system.
- A database-level partial unique index enforces exactly one
  `is_current=true` row per profile — closing the gap Day 16 explicitly left
  open (transaction-ordering only, no DB constraint).
- Historical rows are preserved on regeneration; explicitly does not feed
  synthesis into Opportunity scoring/rationale (Day 18).

Verification: 12 new tests (`tests/test_content_intelligence_synthesis.py`)
plus the full 266-test regression suite passing, Ruff check/format clean,
single migration head (`q0r1s2t3u4`), and an independent architecture review
(verdict PASS) checked specifically for a repeat of Day 16's cache-key-
ownership-bypass bug class, cross-tenant `workspace_id` corruption, and
LLM-fabricated lineage — none found.

### 2026-09-14 amendment — Cold-Start / Activation Mode (post-implementation patch)

Both the Day 16 (Intelligence Reasoning Layer) and Day 17 (Content
Intelligence Synthesis Engine) work above were patched after shipping,
because new creator profiles were being incorrectly treated as
data-insufficient despite already having enough profile-stated context
(stated positioning, stated topics/expertise, stated target audience) for a
full recommendation immediately after onboarding — only Performance
Intelligence is legitimately unavailable for a brand-new profile, since no
content has been published yet.

- **Day 16 patch:** `audience_analysis` and `market_analysis` grounding
  (`app/services/intelligence/grounding.py`) now also accepts onboarding
  -stated profile data (stated target-audience description, stated topics,
  stated expertise, stated positioning) as valid grounding when no
  persona/pain-point or topic/market-signal history exists yet — the
  previous minimum-record-count check treated "no accumulated signal
  history" and "no data at all" as the same case. A new `grounding_basis`
  column (`stated` | `observed` | `mixed`) on `AudienceAnalysis` and
  `MarketAnalysis` records which kind of data grounded the analysis.
  Migration `s2t3u4v5w6` adds the column and backfills every pre-existing
  `ai`/`ai_fallback` row to `observed` (the stated-data grounding path did
  not exist before this patch, so no pre-existing row could have been
  `stated`); `insufficient_data` rows are left `NULL`.
- **Day 17 patch:** `strategic_synthesis` (`app/content_intelligence/`) now
  distinguishes genuine insufficient data (Brand, Audience, or Market also
  thin/missing — unchanged `generation_source=insufficient_data` fallback)
  from cold start (Brand, Audience, and Market all present and grounded,
  Performance absent specifically because the profile has zero
  `PublishedContent`/`ContentPerformance` rows — verified directly by query,
  never inferred from Performance analysis being null alone). Cold start
  runs as a full `generation_source=ai` call with an activation-framed
  prompt addendum (`COLD_START_PROMPT_ADDENDUM` in
  `app/content_intelligence/reasoner.py`) that frames the absence of
  performance history as expected and asks for an opportunity/activation
  -focused first-content recommendation, never fabricated performance data.
  A new `cold_start` boolean column on `ContentIntelligenceSynthesis`
  (migration `t3u4v5w6x7`, default `false`, backfilled `false` for every
  pre-existing row — historical rows are not retroactively reclassified)
  records this. `is_stale`/lazy-regeneration behavior is unchanged: once a
  profile publishes its first content, the existing staleness mechanism
  naturally triggers regeneration that produces `cold_start=false`. Day 18's
  `opportunity_reasoning` was not modified by this patch — it consumes
  `ContentIntelligenceSynthesis` as-is and will pick up `cold_start`
  automatically.

Regression coverage for the genuine-insufficient-data case was confirmed
preserved: the full pre-existing Day 16/17 test suite passes unchanged (no
test's asserted outcome changed), plus new tests cover stated-only
grounding (`test_stated_only_grounding_for_new_profile`), cold-start
synthesis (`test_cold_start_synthesis_runs_as_full_ai_generation`), and
cold start flipping to `false` after first publish
(`test_cold_start_becomes_false_after_first_publish`). Full suite: 279
tests passing (275 pre-existing + 4 new), Ruff check/format clean, two new
migration heads (`s2t3u4v5w6`, `t3u4v5w6x7`) chained after `r1s2t3u4v5`.

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
        +-- Content Intelligence Synthesis (reads across all four above)
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
module described below. Day 16 (Intelligence Reasoning Layer) added
`brand_analysis`, `audience_analysis`, and `market_analysis` as three more
tables FK'd to `ContentProfile.id`, one per Brand/Audience/Market
Intelligence node in the tree above — each storing that domain's latest
LLM-reasoned analysis rather than being part of the domain's own data
model. Day 17 (Content Intelligence Synthesis Engine) added
`content_intelligence_synthesis`, also FK'd to `ContentProfile.id`, but
unlike every prior analysis table it is not scoped to one Intelligence
domain — it reads across `brand_analysis`, `audience_analysis`,
`market_analysis`, and `performance_insight` at once, making
`app/content_intelligence/` the first domain module organized around
cross-domain reading rather than living inside a single Intelligence
domain.

## Day 18 - Opportunity Reasoning Upgrade

Gave `ContentOpportunity.strategic_rationale` its first LLM reasoning layer,
grounded in the Day 17 `ContentIntelligenceSynthesis`, without changing the
opportunity score, score components, priority mapping, or ranking, which
remain entirely deterministic (`app/ai/strategy/opportunity_scorer.py` was
not modified).

- New `opportunity_reasoning` AI task (`app/services/llm/opportunity_reasoner.py`,
  `app/services/opportunity_reasoning.py`), registered in
  `TASK_PROVIDER_POLICY` alongside the Day 16/17 reasoning tasks. Input is
  the opportunity's deterministic score components (read from
  `opportunity_metadata`, never recomputed) plus the profile's current
  `ContentIntelligenceSynthesis`; output is a natural-language
  `strategic_rationale`. A synthesis only counts as grounding if it exists
  and its `generation_source` is `ai`/`ai_fallback` — an `insufficient_data`
  synthesis is excluded, mirroring Day 17's own component-availability rule.
- Two new `ContentOpportunity` columns: `rationale_generation_source`
  (`ai` | `deterministic`) and `rationale_generated_at`. No score-related
  column was added or changed.
- Deterministic-first, adapted to async (mirrors the Day 11/12 brief/draft
  pattern): `ContentOpportunityService.create` persists the opportunity
  immediately with its existing templated placeholder rationale
  (`rationale_generation_source=deterministic`, `rationale_generated_at=null`)
  — the opportunity is usable the instant it's created, never blocked on an
  LLM call — then enqueues exactly one `opportunity_reasoning` job (Day 15
  queue) per opportunity in the same transaction. The job
  (`generate_rationale`) either updates `strategic_rationale` in place and
  sets `rationale_generation_source=ai`, or, if no substantive synthesis
  exists yet or the AI provider fails, leaves the deterministic placeholder
  as final. There is deliberately no separate `ai_fallback` value: in both
  fallback cases the persisted text is the same deterministic template, not
  a degraded AI output.
- Bulk opportunity creation fans out one independent job per opportunity —
  each call to `ContentOpportunityService.create` enqueues its own job; there
  is no code path that loops over several opportunities and blocks on AI
  calls synchronously.
- Per-profile rate limiting on `opportunity_reasoning` job execution reuses
  the Day 15 sliding-window limiter (`rate_limit_reasoning_requests_per_window`,
  new setting), applied inside the worker rather than the HTTP middleware. A
  new `RateLimitDeferredError` (`app/infrastructure/ratelimit/errors.py`) is
  raised by the job handler when a profile is over budget;
  `execute_ai_job` (`app/infrastructure/jobs/worker_tasks.py`) special-cases
  this exception — distinct from a handler failure — by undoing the attempt
  count and requeueing the job via arq's `_defer_by`, so a burst of new
  opportunities for one profile queues excess reasoning jobs rather than
  dropping or failing them.
- `strategic_rationale`, `opportunity_score`, `relevance_score`, `priority`,
  and `opportunity_metadata.score_components` are read by the reasoning job
  but never written to by it except `strategic_rationale` itself — verified
  by an explicit regression test asserting all four are byte-identical
  before and after the reasoning job runs, alongside the full pre-existing
  Day 7/14 opportunity scoring test suite passing unchanged.
- Migration `r1s2t3u4v5` adds the two new columns (plus an index on
  `rationale_generation_source`) to `content_opportunities`. Reversible.

Verification completed with:

- 9 new tests in `tests/test_opportunity_reasoning.py`: instant creation with
  a usable deterministic placeholder, async reasoning updating the rationale
  in place, content correspondence between the reasoner's input context and
  the real synthesis summary/score components (not hallucinated), the
  no-synthesis-yet fallback, the AI-provider-failure fallback, an
  `insufficient_data` synthesis correctly not counting as available,
  score/priority/score-components byte-identical before and after
  reasoning, bulk creation producing independent per-opportunity jobs rather
  than a blocking loop, an end-to-end `execute_ai_job` round trip, and the
  rate limiter deferring (not dropping) an over-budget job.
- Full repository regression suite passing: 275 tests. The existing
  `create_opportunity` endpoint now requires an arq pool to fan out the
  reasoning job, so `tests/conftest.py` gained a new autouse
  `_default_arq_pool_override` fixture (a mocked pool for every test in the
  suite, mirroring the Day 17 synthesis test file's own override) — every
  other test file that creates opportunities through HTTP (briefs, drafts,
  variations, evaluations, library, published content, audience signals)
  needed no changes itself.
- Ruff check and format check clean for all Day 18 files.
- Migration chain validated with a single head (`r1s2t3u4v5`); not run
  against a real PostgreSQL instance, matching the project's existing
  SQLite-vs-Postgres testing convention (no Postgres available in this
  development environment).
- All pre-existing Day 7/14 opportunity scoring/ranking tests pass with
  unchanged outcomes.

## Day 19 - Content Library (Production-Grade Retrieval)

Upgraded the Day 16 Content Library retrieval layer over `ContentDraft` for
concurrent read load, replacing offset pagination and `ILIKE` search with
mechanisms that don't degrade at scale. No new domain model was introduced;
`ContentDraftRepository`/`ContentLibraryService` still compose queries over
the existing `ContentDraft` table, matching Day 16's original design intent.

- **Cursor pagination**: `GET /api/v1/library` now takes an opaque `cursor`
  (base64 of `{sort_by, sort_order, sort_key, id}`) instead of `skip`/`limit`.
  Offset pagination was removed entirely from this endpoint (not just
  deprecated) because it degrades under concurrent writes and large tables.
  Every query orders by `(sort_column, id)` — `id` as a permanent secondary
  sort key, whether or not a cursor is present — so rows sharing an
  identical `created_at`/`updated_at` still get a total, stable order. The
  boundary condition is `sort_column < cursor_value OR (sort_column =
  cursor_value AND id < cursor_id)` (reversed for ascending sort), built
  with plain `OR`/`AND` rather than SQL row-value comparison, so it needs no
  dialect-specific tuple-comparison support. `InvalidCursorError` (a
  `ValueError` subclass) is raised for a malformed cursor or one whose
  `sort_by`/`sort_order` no longer matches the request, and maps to `400`
  distinctly from the `404` used for ownership failures.
- **Composite index**: migration `u4v5w6x7y8` adds
  `ix_content_drafts_profile_status_created_id` on
  `(profile_id, status, created_at DESC, id)`, mirrored in the
  `ContentDraft` model's `__table_args__` so the SQLite test schema
  (built via `Base.metadata.create_all`) carries the same index shape.
- **Full-text search**: on Postgres, `content_drafts.search_vector` is a
  `GENERATED ALWAYS AS (to_tsvector('english', title || hook || caption))
  STORED` column (added by raw SQL in the same migration, guarded by a
  `bind.dialect.name == "postgresql"` check — a real generated column,
  preferred over an application trigger per the day's spec) with a GIN
  index, queried via `search_vector @@ plainto_tsquery(...)`. The
  `ContentDraft` model declares `search_vector` as
  `TSVECTOR().with_variant(Text(), "sqlite")`, never assigned to from
  Python, so the ORM never fights Postgres's own generated value. On
  SQLite (this project's test database, per its established Postgres/SQLite
  testing convention — see "Known Limitations") the column is a plain,
  always-`NULL` text column, and `ContentDraftRepository._search_clause`
  branches on `session.get_bind().dialect.name` to fall back to
  `ILIKE`/`LIKE` there — meaning GIN index usage itself is asserted by the
  migration/model, not exercised by the test suite, matching the same
  documented gap as the Day 13 partial-unique-index and Day 15
  connection-pool settings.
- **Hard max page size**: `page_size` is clamped server-side to
  `settings.content_library_max_page_size` (default 50) in both the router
  and the service, regardless of what the client requests — a
  `page_size=1000` request silently returns at most 50 rows rather than
  erroring or returning everything.
- **Default-view cache**: `GET /api/v1/library` read-through-caches only
  the fully unfiltered, first-page (`cursor=None`), default-sort
  (`created_at desc`), default-page-size view — the highest-traffic query
  pattern — following the exact router-level Redis pattern already used by
  `app/api/v1/intelligence_analysis.py` (`get_redis()` called directly in
  the route handler, not injected via `Depends`). The cache key is
  `workspace:{workspace_id}:library:default:page_size={page_size}`;
  `workspace_id` is part of the key (not just checked after a hit) so a
  cache hit can never cross a tenant boundary. TTL is a new
  `library_default_view_cache_ttl_seconds` setting (default 30s) —
  deliberately much shorter than the general `cache_default_ttl_seconds`
  (300s) since drafts change often. Any other filter/sort/cursor/page_size
  combination bypasses the cache entirely (read and write). Draft create
  (`ContentCreationService.create`), draft update
  (`ContentCreationService.update`), and variation selection
  (`ContentDraftVariationService.select`, which syncs a selected variation
  into `ContentDraft.hook`/`caption` per Day 13) each call a new
  `invalidate_library_cache(workspace_id)` helper
  (`app/services/content_library.py`) after `commit()`, which drops every
  cached library key for that workspace via the Day 15 `CacheService`'s
  `invalidate_prefix` (non-blocking `SCAN`, not `KEYS`).
- Because cache invalidation is now reachable from the widely-shared draft
  create/update/variation-selection code paths, `tests/conftest.py` gained
  a new autouse `_default_cache_redis_override` fixture (mirroring the Day
  18 `_default_arq_pool_override` pattern) that patches
  `app.services.content_library.get_redis` to a `fakeredis` instance for
  every test in the suite — no real Redis is available in this development
  environment. `tests/test_content_library.py` additionally patches the
  same target plus `app.api.v1.content_library.get_redis` with its own
  fake instance to assert on cache hits and invalidation directly.

Verification completed with:

- 11 tests in `tests/test_content_library.py`: filters/sorting, cursor
  pagination across three pages with no gap/overlap, an explicit
  concurrent-insert-between-page-fetches scenario proving the cursor is
  unaffected by a row landing at the very top of the default (newest-first)
  order — the exact failure mode offset pagination is prone to — an
  invalid/malformed cursor rejected with `400`, a cursor rejected with
  `400` when reused against a different `sort_by`, max-page-size
  enforcement (`page_size=1000` capped to 50 with 60 drafts present),
  date-range filters, search matching title/hook/caption, lineage
  retrieval, cross-workspace/cross-profile isolation (`404`), the
  empty/unknown-draft paths, and default-view cache-hit-then-invalidation
  on create.
- Full repository regression suite passing: 284 tests (275 pre-existing +
  9 net new — 6 Day 16 tests were rewritten in place for the new response
  shape rather than added alongside the old ones).
- Ruff check and format check clean for all touched Day 19 files
  (`app/models/content_draft.py`, `app/repositories/content_draft.py`,
  `app/services/content_library.py`,
  `app/services/content_creation/service.py`,
  `app/services/content_creation/variation_service.py`,
  `app/api/v1/content_library.py`, `app/schemas/content_library.py`,
  `app/core/config.py`, `tests/test_content_library.py`,
  `tests/conftest.py`, and the new migration).
- Migration chain validated with a single head (`u4v5w6x7y8`); the
  Postgres-only DDL branch (generated `search_vector` column, GIN index)
  was not run against a real PostgreSQL instance, matching this project's
  existing SQLite-vs-Postgres testing convention (no Postgres available in
  this development environment) — the same documented gap as Day 13's
  partial unique index and Day 15's connection pool/statement-timeout
  settings.

Known follow-up (should-fix, not addressed this day): variation generation
(`ContentDraftVariationService.generate`, which does not itself mutate
`ContentDraft` fields) does not invalidate the library cache, since it
never changes what `/library` would return; only `select` (which does
mutate `hook`/`caption`) does. If a future day changes `generate` to touch
draft-level fields, it should call `invalidate_library_cache` too.

## Day 20 - Authentication Foundation: JWT Issuance, Refresh & Redis-Based Revocation

Added the system's first real authentication layer. Full spec:
`docs/development/day-20.md`.

**Scope correction made at the start of this day**: code inspection
confirmed there is no ownership-chain enforcement anywhere in the
codebase — `WorkspaceMember.user_id` is a bare `String(255)`, not a
foreign key; every Day 15-19 router trusts a client-supplied
`workspace_id`/`profile_id` with no verification; the Day 15 rate
limiter's identity was an `X-User-Id` header or client IP. This is a live
IDOR vulnerability, independent of JWT auth. Day 20 was scoped to
Authentication only, with one exception: patching the Day 15 rate
limiter's identity source. No ownership-chain retrofit was performed on
Days 15-19 routers.

- New `app/auth/` module: `User`, `RefreshToken`, `PasswordResetToken`
  models; argon2 password hashing with a documented cost factor; opaque,
  high-entropy refresh/reset tokens (`secrets.token_urlsafe(48)`) stored
  server-side only as a SHA-256 hash.
- `POST /auth/login` issues a short-TTL JWT access token (HS256; a single
  backend serves this MVP, so asymmetric signing isn't yet justified) plus
  a longer-TTL opaque refresh token. `POST /auth/refresh` rotates the
  refresh token on every use, grouped by `session_id`; presenting an
  already-rotated (reused/stale) token revokes the entire session rather
  than just rejecting that one token — defense-in-depth against a stolen
  token being replayed after rotation. `POST /auth/logout` adds the access
  token's `jti` to Redis (`revoked_jti:{jti}`, TTL = its remaining
  validity, self-expiring) and revokes the refresh token's session,
  reusing the Day 15 shared Redis connection rather than a second client.
- `get_current_user` (`app/auth/dependencies.py`) is the one reusable JWT
  verification dependency — validates signature/expiry, checks the Redis
  revocation list, and returns an `AuthenticatedUser`. Every future
  protected route, including Day 21's ownership-chain checks, is expected
  to depend on this rather than calling `decode_access_token` directly.
  JWT claims are `sub`, `jti`, `iat`/`exp`, and `workspace_ids` — the
  latter is a fast-path hint only, computed from the same unenforced
  `WorkspaceMember.user_id` string match noted above, and is never by
  itself sufficient to authorize access to a specific workspace's
  resource.
- Password reset (`/auth/password-reset/request`, `/auth/password-reset/confirm`)
  is token-based, time-limited, and single-use; the request endpoint
  always returns the same generic message regardless of whether the email
  exists, and email delivery is a structlog stub (`send_password_reset_email`)
  since no email provider is configured anywhere in this stack yet.
- Identical error message (`"Invalid email or password"`) for wrong-password
  and unknown-email, with a dummy-hash `verify_password` call on the
  unknown-email path so the response carries no timing signal about
  account existence.
- `POST /auth/login` is registered under the Day 15 rate-limit middleware
  with its own dedicated, tight policy (`RouteCategory.AUTH_LOGIN`,
  `auth_login_rate_limit_requests_per_window`/`_window_seconds` settings).
- **Rate limiter identity patch**: `app/infrastructure/ratelimit/middleware.py`
  now derives identity from `get_current_user`'s verified JWT (via
  `try_get_request_identity`) when a valid bearer token is present, falling
  back to client IP otherwise. The previous `X-User-Id` header trust was
  removed entirely rather than kept as a secondary fallback — once real
  JWT identity exists, continuing to also trust a client-supplied header
  would be an inconsistent, avoidable downgrade in the identity guarantee
  the limiter is meant to provide.
- Migration `v5w6x7y8z9` (head, down-revision `u4v5w6x7y8`) adds `users`,
  `refresh_tokens`, `password_reset_tokens`. `User.id` is a UUID, matching
  the rest of the codebase's convention and compatible with a future FK
  from `WorkspaceMember.user_id`.
- JWT signing key is environment-driven; `app/core/config.py` rejects the
  built-in insecure default secret outside local development via a
  validator, so a real deployment cannot silently run with a hardcoded key.

### KNOWN CRITICAL GAP

**Days 15-19 accept a client-supplied `workspace_id`/`profile_id` on every
request with no verification that the authenticated caller actually owns
or belongs to that workspace/profile.** `WorkspaceMember.user_id` remains a
bare, unenforced `String(255)` with no foreign key to `User.id`. Day 20
adds real authentication but does **not** retrofit ownership-chain
enforcement onto any existing router — that retrofit is tracked as **Day
21 - Ownership-Chain Enforcement Retrofit**. Days 15-19 must not be
considered auth-complete until Day 21 lands.

Verification completed with:

- 12 new tests in `tests/test_auth.py`: login success/failure, identical
  error message for wrong-password vs. unknown-email, expired-token
  rejection, refresh rotation, reused-stale-refresh-token rejection,
  logout revoking a token with the immediate next request rejected, a
  revoked `jti` present in Redis with the correct remaining TTL, password
  reset end-to-end (including reuse-after-confirm rejected), login rate
  limiting, and the rate limiter keying off real authenticated identity
  rather than a spoofed `X-User-Id` header. All fixtures seed `User`/
  `Workspace` directly (`seed_user`, `seed_workspace` in
  `tests/conftest.py`), matching the Days 15-19 test-seeding convention —
  no signup endpoint exists (MVP: one User maps to exactly one Workspace).
- Full repository regression suite passing: 296 tests.
- Ruff check and format check clean for all Day 20 files.
- Migration chain validated as a single head (`v5w6x7y8z9`) with no
  branching; not run against a real PostgreSQL instance, matching this
  project's existing SQLite-vs-Postgres testing convention (no Postgres
  available in this development environment).
- No ownership-chain regression tests were added — out of scope for this
  day by design (see "KNOWN CRITICAL GAP" above).

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

The following are intentionally outside Days 1-19 (Day 16's Intelligence
Reasoning Layer is covered separately above and closed two of these gaps —
see the note there):

- The Day 17 publish scheduler still deliberately remains its own narrow
  single-table poller rather than routing through the Day 15 job queue.
- `ContentDraftVariationService.generate` does not invalidate the Day 19
  library cache (see Day 19's own "Known follow-up" note above) since it
  never mutates a `ContentDraft` field itself; only variation `select` does.
- Day 19's Postgres-only DDL (the generated `search_vector` column and its
  GIN index) has not been run against a real PostgreSQL instance — GIN
  index usage is asserted by the migration/model, not exercised by the
  SQLite test suite, matching the same documented Postgres/SQLite testing
  gap as Day 13's partial unique index.
- The rate limiter/idempotency-key helpers wired into any real endpoint
  (built and tested in isolation per Day 15, `rate_limit_enabled` defaults
  `False`; Day 16 wired `CacheService` into a real read path, Day 18 wired
  the sliding-window limiter into `opportunity_reasoning` job execution, but
  neither used the idempotency-key helper — see Day 16's known limitations
  above).
- A database-level constraint enforcing "at most one current row" for
  Day 16's per-domain analysis tables — maintained by application-level
  transaction ordering instead (see Day 16 above).
- Retry-on-failure logic for the actual platform publish call, and retracting
  an already-published item.
- Real OAuth flows and real Facebook, Instagram, TikTok, YouTube, LinkedIn, or
  X publishing API calls (`SocialPlatformAdapter.publish` remains a
  manual/no-op placeholder).
- Performance metrics ingestion from published content.
- A learning-alignment scoring factor for `ContentOpportunity` (explicitly
  out of scope for Day 18 — a scoring-formula change, distinct from Day 18's
  rationale-only change).
- Re-triggering `opportunity_reasoning` when an opportunity's
  `target_objective` changes via `PATCH` (Day 18 only reasons at creation).
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
- **Ownership-chain enforcement on Days 15-19 routers** — every existing
  router still trusts a client-supplied `workspace_id`/`profile_id` with
  no verification that the authenticated caller belongs to it;
  `WorkspaceMember.user_id` has no foreign key to `User.id`. Day 20 added
  real authentication but deliberately did not retrofit this. Tracked as
  Day 21 - Ownership-Chain Enforcement Retrofit (see Day 20's "KNOWN
  CRITICAL GAP" note above). Days 15-19 must not be considered
  auth-complete until Day 21 lands.

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

Days 1-19 implement the strategic foundation, intelligence inputs, opportunity
evaluation, brief composition, deterministic and AI-assisted draft creation,
creative variations, quality evaluation, workspace-scoped content library
retrieval, manual/scheduled publish confirmation with cancellation, and (Day
15) reusable platform infrastructure — background jobs, caching, rate
limiting, idempotency, distributed locks, and sized connection pooling.
Day 16's Intelligence Reasoning Layer is the first product feature to
actually consume that Day 15 job queue and cache infrastructure, adding
LLM-reasoned, data-grounded analysis to Brand, Audience, and Market
Intelligence (Performance Intelligence already had this from Day 9). Day 17's
Content Intelligence Synthesis Engine is the first module to read across all
four Intelligence domains at once, combining them into one grounded
cross-domain strategic summary — the architecture's "central brain" concept
given its first real implementation. Day 18 is the first consumer of that
synthesis: `ContentOpportunity.strategic_rationale` gains its own LLM
reasoning layer, grounded in the synthesis plus the opportunity's existing
deterministic score components, generated asynchronously after instant,
non-blocking creation, with a deterministic placeholder as the permanent
fallback whenever no synthesis exists yet or the AI provider fails — the
opportunity's score, score components, priority, and ranking remain entirely
deterministic and unchanged. Day 19 upgrades the Day 16 Content Library into
a production-grade retrieval layer: cursor-based pagination replaces offset
pagination entirely on that endpoint, Postgres generated-column full-text
search replaces `ILIKE`, a composite index supports the default view's
access pattern, and that default view gets the system's first real
read-through cache with explicit invalidation on draft mutation. Day 20
adds the system's first real authenticated-user identity layer — JWT
login/refresh/logout with Redis-based revocation and password reset —
scoped strictly to authenticating an existing user against an existing
workspace (no signup), and repoints the Day 15 rate limiter at that real
identity instead of a client-supplied header. Day 20 explicitly does not
retrofit ownership-chain enforcement onto Days 15-19 (see its "KNOWN
CRITICAL GAP" note); that retrofit is Day 21. No real social platform API
integrations, OAuth flows, advanced media generation, autonomous strategy
features, learning-alignment scoring, or draft editing/publishing changes
were added.
