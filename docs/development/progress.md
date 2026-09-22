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
authenticated identity instead of a client-supplied header. Day 21 (in
progress) retrofits real ownership-chain enforcement onto those
authenticated routes, closing the IDOR gap Day 20 explicitly left open.
Day 22 adds the first signup path (`POST /auth/register`, auto-provisioning
a Workspace with the caller as its owning member) and a step-wise,
resumable onboarding flow that progressively builds that workspace's
first `ContentProfile` across five independently-persisted steps, built
on Day 20's auth primitives and Day 21's ownership-chain foundations.
Day 23 connects the system to the outside world for the first time: real
OAuth 2.0 flows for YouTube, Facebook and Instagram, with an explicit
destination-selection step so each ContentProfile publishes to a specific
Page/Channel rather than merely "the connected account," envelope-encrypted
credential storage, and a scheduled proactive-refresh job. Day 24 wires
those connections into the publish flow — real Facebook Graph API calls,
YouTube/Instagram deliberately fail fast (no video/image asset exists yet),
and due-item promotion moves from an in-process poller to a registered
Day 15 arq periodic job, safe under N concurrent worker instances:

```text
Understand
  -> Decide
  -> Brief
  -> Create
  -> Evaluate
  -> Publish (real for Facebook; manual confirmation elsewhere)
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

**Update:** Day 21 is now in progress (see the "Day 21 - Ownership-Chain
Enforcement Retrofit (in progress)" section below) — the FK, the two
authorization dependencies, and most router/test retrofitting have
landed, but it is not yet complete (see that section's "Remaining work").
Treat this gap as partially, not fully, closed until Day 21's section
above no longer says "in progress."

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

## Day 21 - Ownership-Chain Enforcement Retrofit (in progress)

Retrofits real ownership-chain enforcement onto every Day 15-19 (and
most Day 20) router, closing the IDOR gap Day 20's "KNOWN CRITICAL GAP"
note left open. Full spec: `docs/development/day-21.md`. **This day is
not yet complete** — see "Remaining work" below; this section documents
what has actually landed and been verified so far.

- `WorkspaceMember.user_id` is now a real `UUID` foreign key to
  `User.id` (`ON DELETE CASCADE`), replacing the bare, unenforced
  `String(255)` column noted in Day 20. Migration `w6x7y8z9a0`
  (down-revision `v5w6x7y8z9`) also adds a composite index
  `ix_workspace_members_user_id_workspace_id` on `(user_id,
  workspace_id)`. On PostgreSQL the upgrade raises loudly (rather than
  silently coercing) if any existing row's `user_id` isn't a well-formed
  UUID matching a real `users.id` row.
- New `app/authz/dependencies.py`: `require_workspace_access` verifies
  the authenticated caller (Day 20's `get_current_user`) has a real
  `WorkspaceMember` row for the requested `workspace_id` (via a genuine,
  indexed `(user_id, workspace_id)` query, not a single-workspace
  shortcut); `require_profile_access` composes on top of it to verify a
  requested `profile_id` belongs to that same workspace. Both return
  **404, never 403**, whether the workspace/profile doesn't exist at all
  or exists but isn't the caller's, so cross-tenant resource existence
  is never leaked — matching the architecture's existing ownership-chain
  rule.
- Every Day 15-19 router that previously trusted a client-supplied
  `workspace_id`/`profile_id` now depends on `require_workspace_access`
  or `require_profile_access` instead: `audience_intelligence`,
  `audience_objections`, `audience_questions`, `audience_signals`,
  `brands`, `business_context`, `competitors`, `content_briefs`,
  `content_draft_variations`, `content_drafts`, `content_evaluations`,
  `content_intelligence_synthesis`, `content_library`,
  `content_opportunities`, `content_profiles`, `desires`,
  `intelligence_analysis`, `market_intelligence`, `market_signals`,
  `offers`, `pain_points`, `performance`, `personas`, `products`,
  `published_content`, `services`, `topics`, `workspaces` (`POST
  /workspaces` itself stays undependent — no membership row exists yet
  at creation time; every other `/workspaces/{id}` route depends on
  `require_workspace_access`).
- A genuine pre-existing production regression was found and fixed in
  the same pass: a stray `sort_by` parameter on
  `content_opportunities.list_opportunities` that its repository method
  doesn't accept, causing a `TypeError` at runtime — only surfaced once
  the corresponding test could execute past the newly-enforced auth
  layer to reach it. Confirmed as a genuine regression (not
  pre-existing) against pre-Day-21 `develop` HEAD before fixing.
- Every retrofitted functional test now authenticates as the correct
  owning user before calling a workspace/profile-scoped route, via a new
  `tests/conftest.py` helper, `authenticate_as_workspace_owner(client,
  db_session, workspace_id)`, which seeds a fresh `User` + owning
  `WorkspaceMember` row, mints a JWT, and sets it as the client's
  default `Authorization` header. Cross-tenant isolation tests
  deliberately call it twice (once per workspace) to simulate two
  distinct authenticated users, not just two workspaces.

Verification completed so far (all via actual `uv run pytest` runs, not
assumed):

- `test_audience_intelligence.py`, `test_audience_objections.py`,
  `test_audience_questions.py`, `test_audience_signals.py`,
  `test_brands.py`, `test_competitors.py`, `test_content_briefs.py`,
  `test_content_opportunities.py`, `test_content_profiles.py`,
  `test_desires.py`, `test_market_intelligence.py`,
  `test_market_signals.py`, `test_pain_points.py`, `test_personas.py`,
  `test_topics.py`, `test_content_drafts.py`,
  `test_content_draft_variations.py`, `test_content_evaluations.py`,
  `test_performance.py`, and `test_content_library.py` all retrofitted
  and passing.
- `test_business_context.py`, `test_products.py`, `test_services.py`,
  and `test_offers.py` needed no changes and pass unmodified against the
  retrofitted routers.
- Migration chain validated with a single head (`w6x7y8z9a0`) via
  `uv run alembic heads`.
- Ruff check/format clean for every file touched so far, checked
  individually per file immediately after editing it.

### Remaining work (tracked, not yet done)

- `test_workspaces.py` still fails (5 confirmed failures) against the
  retrofitted `app/api/v1/workspaces.py` — its pre-Day-21 tests never
  authenticate, so `GET`/`PATCH`/`DELETE /workspaces/{id}` now correctly
  return 401 instead of the expected 200/204. Needs the same retrofit
  pattern applied.
- `test_content_intelligence_synthesis.py`, `test_intelligence_analysis.py`,
  `test_published_content.py`, `test_opportunity_reasoning.py`, and
  `test_infrastructure_jobs.py` have not yet been inspected/retrofitted.
- No dedicated per-router "User A cannot access User B's data"
  regression suite has been written yet.
- No dependency-level unit tests exist yet for
  `require_workspace_access`/`require_profile_access` in isolation.
- A full-repository `uv run pytest -q` run (every file) has not been
  completed; only the files listed above have been individually run and
  confirmed.
- Repo-wide `ruff check .` / `ruff format --check .` has not been re-run
  across the whole repository this day.
- The `backend-day` skill's Review step and `/backend-test` have not yet
  been run for this day.

**Days 15-19 and Day 20's own workspace routes should not be considered
ownership-chain-complete until the remaining work above is closed and
this section is updated to reflect it.**

## Day 22 - Registration & Onboarding (Step-Wise, Workspace-Anchored)

Adds the system's first signup path and its first end-user-facing
onboarding flow, built entirely on Day 20's auth primitives and Day 21's
ownership-chain foundations. Full spec: `docs/development/day-22.md`
(inline spec supplied for this day; no separate spec file was checked in
prior to implementation).

**Scope note on Day 21**: this day proceeded without waiting for Day 21's
remaining work (see that section above) to close, per an explicit
decision made at the start of this day — the full baseline suite was run
first and showed 28 pre-existing failures, all in files Day 22 does not
touch (`test_workspaces.py`, `test_intelligence_analysis.py`,
`test_published_content.py`, `test_content_intelligence_synthesis.py`).
Day 22's own Definition of Done language ("full Days 15-21 regression
suite passes unchanged") is satisfied in the sense that matters: the
count and identity of failing tests is unchanged by this day's work, not
in the sense of "zero failures" — that remains Day 21's own outstanding
scope, not Day 22's.

### Section 1 - Registration

- `POST /api/v1/auth/register` (`app/auth/service.py:AuthService.register`,
  wired in `app/api/v1/auth.py`): creates a `User` (reusing Day 20's
  `hash_password`), auto-provisions a `Workspace`
  (`onboarding_status=NOT_STARTED`), creates the sole `WorkspaceMember`
  with `role=WorkspaceRole.OWNER` (the existing Day 2 enum value, not a
  new "owner" role), and issues an access/refresh token pair immediately
  by calling Day 20's existing `_issue_token_pair` directly rather than
  reimplementing token issuance.
- Duplicate-email rejection (409) is enforced both by a pre-check and by
  catching `IntegrityError` on flush/commit and normalizing it to the
  same `EmailAlreadyRegisteredError` — closing the race where two
  concurrent registrations for the same email both pass the pre-check.
  This does not hide account existence the way login's identical-message
  behavior does; the Testing section's requirement was "rejected without
  duplicate records," which this satisfies directly, and a 409 on
  registration is standard practice (a login attempt, not a registration
  attempt, is the enumeration-sensitive surface).
- `/auth/register` is rate-limited via a new
  `RouteCategory.AUTH_REGISTER` in `app/infrastructure/ratelimit/policy.py`
  (exact-path match, mirroring `AUTH_LOGIN`), with its own settings
  (`auth_register_rate_limit_requests_per_window`/`_window_seconds`,
  both defaulting to 5/60s like login).
- Auto-provisioned workspace `name`/`slug` are derived from the email's
  local part plus a random suffix for slug uniqueness
  (`app/auth/service.py:_slug_base`) — there is no other name to draw
  from at registration time; the workspace can be renamed later through
  the existing `PATCH /workspaces/{id}` endpoint.

### Section 2 - Onboarding (step-wise)

- `Workspace.onboarding_status` (`WorkspaceOnboardingStatus`:
  `NOT_STARTED`/`IN_PROGRESS`/`COMPLETED`, default `NOT_STARTED`) lives on
  `Workspace`, not `ContentProfile`, specifically so it is checkable
  before any profile exists — matching the onboarding flow's own `GET`
  endpoint, which must return a status even for a workspace with no
  profile yet.
- New `app/authz/dependencies.py:get_current_workspace` dependency:
  resolves the caller's workspace from their `WorkspaceMember` row alone
  (genuine indexed query by `user_id`, matching Day 21's
  `require_workspace_access` pattern) — no `workspace_id` is accepted
  from the client anywhere in the onboarding router, not even to verify
  against, since MVP (Day 20) is one User per one Workspace.
- New `app/onboarding/` module (`schemas.py`, `service.py`, `router.py`),
  registered in `app/api/v1/router.py`. `OnboardingService` composes the
  existing `ContentProfileService`/`ContentProfileRepository` (Days 2/3),
  `AudienceIntelligenceService`/`PainPointService`/`AudienceQuestionService`
  (Day 4), and `BrandService` (Day 3) for every write — no duplicate
  persistence logic was introduced for any of the four domains onboarding
  touches.
- Five step endpoints, each an independent `PUT` that persists
  immediately and sets `onboarding_status=IN_PROGRESS` the first time any
  step is saved:
  - `/api/v1/onboarding/identity` — creates `ContentProfile`
    (`type=creator`) on first call for the workspace, updates in place on
    resubmission (matched by "the workspace's first/only profile," not a
    stored id, since Model A permits multiple profiles per workspace in
    general but this flow only ever manages the first one).
  - `/api/v1/onboarding/audience` — upserts a single `AudienceIntelligence`
    row (`summary` for the target-audience description,
    `psychographics.interests` for interests) and replaces the profile's
    onboarding-managed `PainPoint`/`AudienceQuestion` rows in full on each
    call (delete-existing-then-recreate) rather than merging, so
    resubmission is idempotent without needing per-item identity from the
    client.
  - `/api/v1/onboarding/goals` — writes into the existing
    `ContentProfile.goals` JSON list (Day 2/3's own goal representation,
    reused directly); constrained to the four spec'd values
    (`growth`/`authority`/`engagement`/`community`) via a new
    `OnboardingGoal` enum in `app/onboarding/schemas.py`.
  - `/api/v1/onboarding/brand` — upserts a single `Brand` row: `tone` maps
    to `Brand.tone["tone_words"]`, `style`/`things_to_avoid` merge into
    `Brand.messaging_guidelines` (merged key-by-key against whatever is
    already stored, so a resubmission that only sends `tone` doesn't wipe
    a previously-saved `style`).
  - `/api/v1/onboarding/platforms` — writes a new
    `ContentProfile.platforms` JSON list column, constrained to the six
    spec'd platforms via a new `OnboardingPlatform` enum.
  - Submitting any step other than identity before identity has ever been
    called raises a 400 (`OnboardingIdentityRequiredError`) rather than a
    404 or a silent no-op, since there is no ownership-chain mismatch
    here — the profile simply doesn't exist yet.
- `GET /api/v1/onboarding` returns `onboarding_status` plus whatever
  partial identity/audience/goals/brand/platforms data exists (each
  section `null` until its step has been saved at least once), reading
  everything fresh through the same service methods the write paths use
  rather than relying on possibly-stale in-memory relationship
  collections (the project's session factory runs with
  `expire_on_commit=False`, so a loaded `AudienceIntelligence.pain_points`
  collection would not reflect a sibling service call's writes without an
  explicit re-query).
- `POST /api/v1/onboarding/complete` checks that every step's required
  sub-fields are present (identity's positioning/primary_niche/topics/
  expertise, goals, platforms, audience's target-audience description
  plus at least one pain point or question, and brand's tone) and returns
  400 with the specific missing list if not; on success sets
  `onboarding_status=COMPLETED` and returns the finished `ContentProfile`
  via the existing `ContentProfileResponse` schema. `BusinessContext` is
  never touched by any onboarding step, so it stays `null` by simple
  omission, not by an explicit guard.

### Schema deviations from the original spec (both confirmed with the
product owner before implementation)

- **`ContentProfile.primary_niche`** (nullable `String(255)`): the spec's
  identity step asks for a "primary niche" field, but no Day 2/3/16
  column represents it (`topics`/`expertise`/`goals` are lists, not a
  single niche statement). Rather than overloading `topics[0]` by
  convention, this day adds a small, dedicated, additive column.
- **`ContentProfile.platforms`** (nullable JSON list): the platforms step
  asks for selected distribution platforms, which has no home anywhere in
  the existing schema (`ContentProfile`, `Brand`, `AudienceIntelligence`)
  — this is genuinely new onboarding-only intent data, not a case of
  reusing an existing sibling structure. Added as a second small,
  additive column in the same migration.

Both are a deliberate, narrow exception to "no ContentProfile schema
change beyond what Days 2/3/16 already defined" — that instruction's
intent (don't duplicate Brand/Audience Intelligence's existing modeling)
doesn't cover fields with no existing home at all.

### Migration

- `x7y8z9a0b1` (head, down-revision `w6x7y8z9a0`) adds
  `workspaces.onboarding_status` (enum, default `not_started`),
  `content_profiles.primary_niche` (nullable string), and
  `content_profiles.platforms` (nullable JSON/JSONB). Reversible; single
  head confirmed via `uv run alembic heads`.
- No unique constraint was added anywhere limiting a `Workspace` to one
  `ContentProfile` — confirmed by inspection that Day 2/3's model never
  had one (Model A was already satisfied before this day started).

### Files changed

- New: `app/onboarding/__init__.py`, `app/onboarding/schemas.py`,
  `app/onboarding/service.py`, `app/onboarding/router.py`,
  `migrations/versions/x7y8z9a0b1_add_onboarding_status_and_profile_fields.py`,
  `tests/test_registration.py`, `tests/test_onboarding.py`.
- Modified: `app/models/workspace.py` (`WorkspaceOnboardingStatus` +
  column), `app/models/content_profile.py` (`primary_niche`/`platforms`
  columns), `app/models/__init__.py` (registers the new enum),
  `app/schemas/content_profile.py` and `app/api/v1/content_profiles.py`
  (expose the two new fields on the existing CRUD endpoints, since the
  model gained them), `app/services/content_profile.py` (accepts the two
  new fields in `create`/`update`), `app/auth/schemas.py`
  (`RegisterRequest`), `app/auth/service.py` (`register`,
  `EmailAlreadyRegisteredError`, `_slug_base`), `app/api/v1/auth.py`
  (`/auth/register` route), `app/authz/dependencies.py`
  (`get_current_workspace`), `app/infrastructure/ratelimit/policy.py`
  (`RouteCategory.AUTH_REGISTER`), `app/core/config.py` (register
  rate-limit settings), `app/api/v1/router.py` (registers the onboarding
  router).

### Testing

23 new tests: `tests/test_registration.py` (5 — user/workspace/owner
membership creation, duplicate-email rejection without duplicate
records, case-insensitive duplicate detection, register-endpoint rate
limiting, and a freshly-registered workspace reporting `not_started`
onboarding status) and `tests/test_onboarding.py` (9 — unauthenticated
rejection, identity step creating a profile and flipping status to
`in_progress`, out-of-order audience-before-identity rejected with 400,
resubmitting identity updating in place with no duplicate profile row,
a full five-step flow through `/complete`, `/complete` rejecting on
missing required fields, a resumed session seeing prior partial data via
`GET`, `BusinessContext` confirmed absent (404) after a completed
onboarding, and cross-user isolation — a second registered user sees a
fresh `not_started`/empty onboarding state, never the first user's data).

Full-repository regression: `uv run pytest -q` — 282 passed, 28 failed
(268 pre-existing passing + 14 net new from this day's two test files;
the 28 failures are byte-identical by test name to the pre-Day-22
baseline captured at the start of this day — same 28, same files,
nothing added or removed; see the Day 21 section above). Ruff check and format check clean for every file this day
touched (verified individually and confirmed the 15 repo-wide `ruff
check` findings and 25 repo-wide `ruff format --check` findings are all
in pre-existing files this day never touched). Migration chain validated
as a single head (`x7y8z9a0b1`) via `uv run alembic heads`; not run
against a real PostgreSQL instance, matching this project's existing
SQLite-vs-Postgres testing convention.

### Known limitations carried forward

- The 28 pre-existing Day 21 test failures remain open — this day did
  not attempt to close them (explicit scope decision; see the note at
  the top of this section). See the Day 21 section above for the file
  list and remaining work.
- `WorkspaceOnboardingStatus`/onboarding fields have not been exercised
  against a real PostgreSQL instance (same documented convention as
  every prior day's enum/JSONB additions).
- Onboarding's audience-step "replace in full" semantics for pain
  points/questions means any pain point or question added to a profile
  through the general-purpose Day 4 CRUD APIs
  (`/personas`, `/pain-points`, `/audience-questions`) during an
  in-progress onboarding would be silently deleted by the next audience
  step submission. Not a concern for this day's actual flow (nothing
  calls those APIs during onboarding), but worth flagging before any
  future day lets onboarding and direct intelligence editing overlap.
- No endpoint exists yet to create a workspace's second or later
  `ContentProfile` (explicitly out of scope for this day per Model A's
  note); the schema does not block it, but no service/router path
  creates it.

## Day 23 - Platform Connections: OAuth for YouTube, Facebook & Instagram

Adds real OAuth 2.0 connect/disconnect flows for YouTube, Facebook and
Instagram, with encrypted credential storage and proactive refresh, and
gives the Day 9 `SocialPlatformAdapter` contract its first real
implementations — **connection/authorization surface only**. No publish
call is wired (Day 24).

### The central design point: one login is not one destination

A person has one Facebook login but may administer several Pages; one
Google login but may manage several YouTube channels (including Brand
Account channels); Instagram publishing runs through a Business Account
linked to a *specific* Page. Because a Workspace can hold several
`ContentProfile`s (Model A), two profiles in one workspace may
legitimately need to publish to two **different** Pages/Channels through
the **same** underlying social login.

The flow therefore has three steps, not two, with an explicit
destination-selection step between token exchange and persistence:

```text
1. authorize          -> signed CSRF state + allowlisted authorization URL
2. callback           -> USER-level token + the list of destinations that
                         account administers.  PERSISTS NOTHING.
3. select-destination -> resolve the DESTINATION-scoped token for one
                         chosen Page/Channel, then persist the connection
```

Step 2 deliberately stops short of persistence. Collapsing 2 and 3 —
persisting whichever destination the platform happened to return first —
is the exact bug this day exists to prevent, and it is the bug a
single-destination test account would never reveal.

### PlatformConnection model

`app/platform_connections/models.py`, table `platform_connections`:
`workspace_id`, `profile_id`, `platform` (`youtube`|`facebook`|
`instagram`), `external_account_id`, `external_account_name`,
`access_token_encrypted`, `refresh_token_encrypted`, `token_expires_at`,
`scopes_granted`, `status` (`connected`|`disconnected`|`expired`|
`revoked`), `connected_at`, `last_refreshed_at`, JSONB `metadata`,
`created_at`/`updated_at`.

- `external_account_id` is always the **specific destination** — a Page
  ID, a YouTube Channel ID, or an Instagram Business Account ID — never
  the top-level user/account id the OAuth login authenticated as.
- **Unique constraint on `(profile_id, platform)`, NOT
  `(workspace_id, platform)`** — under Model A two profiles in one
  workspace each hold their own independent connection. Reconnect
  replaces that row in place rather than duplicating it.
- Index on `(status, token_expires_at)` serves the refresh job's due-item
  query.
- **Naming deviation from the day spec**: the token columns are
  `access_token_encrypted`/`refresh_token_encrypted` rather than the
  spec's bare `access_token`/`refresh_token`. Same fields, same
  encryption requirement; the suffix makes the at-rest ciphertext
  obvious at every call site.
- `__repr__` deliberately excludes every token column, so a repr in a
  traceback or log line can never carry a credential.

### Per-platform token lifecycle (genuinely not uniform)

This was confirmed per platform rather than assumed identical, and the
nullable columns reflect real differences:

- **YouTube/Google**: short-lived access token (~1h) plus a long-lived
  refresh token, returned only when the authorization request carries
  `access_type=offline&prompt=consent` (both are sent). Google issues
  **no per-channel credential** — the account token authorizes uploads
  and the channel choice rides on `external_account_id` alone. So a
  YouTube row legitimately stores an account-scoped token, recorded
  explicitly as `connection_metadata.token_scope="account"`.
- **Facebook/Instagram**: the code exchange yields a short-lived user
  token, immediately upgraded to a long-lived one (~60 days) via
  `grant_type=fb_exchange_token`, because Page tokens derived from a
  long-lived user token **do not expire**. There is no refresh-token
  grant at all, so `refresh_token_encrypted` and `token_expires_at` are
  legitimately NULL. The **Page-scoped** token is what gets stored; the
  user-level token is never persisted to Postgres.
- Whether a platform issues a destination-scoped credential is a
  **declared provider property** (`issues_destination_token`), never
  inferred from whether a token happened to appear in the response — see
  the review findings below.

### Destination fetching

- **Facebook**: `GET /me/accounts` returns every administered Page with
  its own Page Access Token in the same response. A Page with no
  `access_token` is filtered out rather than offered.
- **Instagram**: the same `/me/accounts` call, requesting the
  `instagram_business_account` field per Page. A Page with no linked
  Business Account is excluded entirely — it would look connectable and
  then fail at publish time. `external_account_id` is the Instagram
  Business Account ID; the originating Page ID is kept in `metadata`.
- **YouTube**: `channels.list(mine=true)`, returning every channel the
  Google account manages, Brand Accounts included.
- An account with zero publishable destinations gets a 422 with a clear
  message, and no credential is parked in Redis.

### Pending-connection state (Redis, Day 15 connection)

`app/platform_connections/pending.py` holds the user-level token and
fetched destination list under a one-time `selection_token`, TTL 600s
(`oauth_pending_connection_ttl_seconds`). Every token in the blob —
the user token *and* each per-destination Page token — is
envelope-encrypted before it reaches Redis; "it's only there for ten
minutes" was not treated as a reason to hold a live credential in the
clear. `consume` uses `GETDEL`, so the selection token is genuinely
single-use and a replay finds nothing. An abandoned OAuth attempt simply
expires: nothing was written to Postgres, so nothing needs cleaning up.

### Token encryption (envelope, rotation-compatible)

`app/platform_connections/crypto.py`. A fresh 256-bit DEK per encryption
call AES-256-GCMs the token; the DEK is itself wrapped under a KEK from
`settings.token_encryption_keys`. Only wrapped DEKs are stored; the KEK
never touches Postgres or Redis. A bare database column (or Postgres-side
`pgcrypto`) was rejected deliberately — the key would then travel through
the database, so a backup or read replica would carry decryptable
credentials.

Ciphertext format:

```text
v1.<key_id>.<b64url(wrap_nonce||wrapped_dek)>.<b64url(data_nonce||ciphertext)>
```

**Key rotation compatibility** (rotation itself out of scope this day):
`token_encryption_keys` is a keyring (`key_id -> base64 key`), not a
single key, and every stored blob names the `key_id` that wrapped its
DEK. A rotation is therefore: add the new key alongside the old and
repoint `token_encryption_active_key_id` (reads keep working
immediately, since old blobs resolve their own key id); re-encrypt at
leisure, or lazily on the next token refresh, which already runs
decrypt+encrypt; drop the retired key once nothing references it. No
column, migration, or table rewrite, and no re-encryption inside the
rotation window. DEKs are per-value and already rotate on every write.

### Endpoints (all Day 21-guarded)

Every route is nested under `/profiles/{profile_id}/...` so Day 21's
`require_profile_access` applies natively; `workspace_id` remains a query
parameter validated by `require_workspace_access`, matching the
established convention of every other profile-scoped router. No route
trusts a bare client-supplied `workspace_id`/`profile_id`.

```text
POST   /api/v1/profiles/{profile_id}/platform-connections/{platform}/authorize
POST   /api/v1/profiles/{profile_id}/platform-connections/{platform}/callback
POST   /api/v1/profiles/{profile_id}/platform-connections/{platform}/select-destination
GET    /api/v1/profiles/{profile_id}/platform-connections
DELETE /api/v1/profiles/{profile_id}/platform-connections/{platform}
```

No endpoint accepts or returns a token; `PlatformConnectionResponse` has
no token field at all, so a credential cannot leak by accidental
omission.

### Security

- **CSRF state** (`state.py`): HMAC-SHA256-signed, expiring, carrying the
  target `profile_id`. Signed with a dedicated `oauth_state_secret`
  (falling back to the JWT secret only in development) so a
  state-signing compromise never implies an access-token-forging one.
  Every failure mode raises the same message, so probing reveals nothing
  about which check failed.
- **Layered re-verification**: a valid signature proves only that *we*
  issued the state, not who is presenting it. So the state-encoded
  `profile_id` is cross-checked against the path `profile_id` the caller
  already passed `require_profile_access` for — at the callback **and
  again at destination selection**, against the pending state. A forged
  or replayed state cannot attach a connection to a profile the caller
  doesn't own.
- **Redirect URI allowlist**: exact list membership, never a
  prefix/`startswith` test (which would accept
  `https://app.example.com.evil.test/` and hand the authorization code
  to an attacker).
- **Minimum viable scopes** — YouTube: `youtube.readonly` (needed to
  enumerate channels at all) + `youtube.upload` (narrowest publish
  scope, not the broad `youtube`). Facebook: `pages_show_list`,
  `pages_read_engagement`, `pages_manage_posts`. Instagram:
  `pages_show_list`, `pages_read_engagement`, `instagram_basic`,
  `instagram_content_publish`. No ads, insights, messaging or
  user-profile scopes anywhere.
- **Config validation**: outside development, `Settings` rejects the
  built-in development KEK, an unset `oauth_state_secret`, the default
  localhost redirect allowlist, and any non-`https` redirect entry —
  mirroring the existing `jwt_secret_key` validator.

### Disconnect

Revokes with the platform where supported, then **hard-deletes** the row
— never a soft-delete of a live credential. Google supports real
revocation (`oauth2.googleapis.com/revoke`). Facebook/Instagram
revocation is **best-effort**: full app de-authorization needs the *user*
token, which this day deliberately never persists, so `DELETE
/me/permissions` is attempted with the Page token. The local credential
is deleted regardless of what the platform answers, including when it is
unreachable.

### Proactive refresh (Day 15 scheduled job)

`app/platform_connections/refresh.py`, registered as an arq **cron job**
in `WorkerSettings.cron_jobs` (every 15 minutes, comfortably inside the
default 1-hour `platform_connection_refresh_threshold_seconds`, so a
near-expiry token gets several attempts before it can lapse). A cron job
rather than a queued `execute_ai_job` task type because nothing submits
it — it is time-driven, not request-driven, with no per-profile job row
to track. It is not a second scheduler and not an in-process API poller
like Day 17's `PublishScheduler`.

On failure the connection is marked `status=expired` with the reason in
its metadata, rather than left looking `connected` to fail opaquely at
publish time — the "durable, visible failure state" rule from the
architecture's **AI Execution and Job Control** section. Each connection
is refreshed and committed independently, so one bad credential cannot
stop the rest of the batch. Rows with a NULL `token_expires_at` (a
non-expiring Page token) are excluded from the due query on purpose.

### Platform adapters (Day 9 contract)

`app/platform_connections/adapters.py`: `YouTubeAdapter`,
`FacebookAdapter`, `InstagramAdapter`, behind a
`PlatformConnectionAdapter` Protocol that literally extends Day 9's
`SocialPlatformAdapter`. Implements the connection/authorization surface
Day 9 anticipated (`authorization_url`, `exchange_code`,
`list_destinations`, `refresh_token`, `disconnect`, `access_token`).
`publish` is a typed stub that **raises** — a stub returning a plausible
success would be worse than one that refuses, because Day 24 would then
have nothing to notice. `get_adapter` is the uniform lookup Day 24 will
consume connections through; `access_token` refuses a connection that
isn't `connected`, so an expired credential fails loudly here rather than
as an opaque platform 401 later.

### Migration

`y8z9a0b1c2` (head, down-revision `x7y8z9a0b1`) creates
`platform_connections` with the `(profile_id, platform)` unique
constraint, the `(status, token_expires_at)` composite index, and
`workspace_id`/`profile_id` indexes. Reversible (table, 3 indexes and
both enum types created and dropped symmetrically). Single head confirmed
via `uv run alembic heads`.

### Review findings found and fixed

An independent architecture/security review ran before testing and
returned **PASS WITH CHANGES**. One blocking issue and several
should-fixes were found and fixed in the same pass:

- **BLOCKING — migration enum labels would have broken the feature on
  PostgreSQL.** `SqlEnum(PyEnum)` persists the member **name**
  (`'YOUTUBE'`), but the migration created the Postgres types with
  lowercase `.value` labels (`'youtube'`), plus
  `server_default="connected"`. Every insert would have raised `invalid
  input value for enum socialplatform: "YOUTUBE"` on the real database.
  The SQLite test suite structurally **cannot** catch this — SQLite
  renders `Enum` as `VARCHAR + CHECK` built from the same model
  metadata, so both sides agree there and the suite stays green while
  production is broken. Fixed to uppercase member names, matching the
  repo's own precedent (`o8p9q0r1s2` uses `"QUEUED"`, `e7f8a9b0c1d2`
  uses `"DRAFT"`). A new test,
  `test_migration_enum_labels_match_what_sqlalchemy_binds`, compares the
  migration's literals against the ORM's actual bind output and was
  verified to fail against the old lowercase values — closing the blind
  spot without needing a live Postgres.
- **Destination-scoping was inferred, not declared.**
  `destination_scoped = destination.access_token is not None` meant a
  Facebook/Instagram Page that returned no `access_token` (which
  `/me/accounts` does whenever the caller's role or granted scopes don't
  yield one) would silently fall through to persisting the long-lived
  **user** token while stamping `token_scope="account"` as though
  intentional — defeating the day's central security property and
  leaving us holding an app-wide credential covering every Page the
  person administers. Fixed: `issues_destination_token` is now a
  declared per-provider property; such Pages are filtered out of
  `list_destinations`, and `_persist_connection` raises
  `MissingDestinationTokenError` rather than falling back.
- **Concurrent selection raised an unhandled `IntegrityError` (500).**
  Two selections for the same `(profile, platform)` both read "no
  existing row" and both insert. Now normalized to a 409
  `ConnectionConflictError`, matching the Day 13 variation-selection
  precedent.
- **A 2xx platform response with an unexpected body raised a bare
  `KeyError` (500)** instead of the module's deliberate 502. Added
  `require_access_token`, used by both the Google and Facebook token
  paths.
- **Config hardening**: the redirect-URI allowlist is now validated
  outside development (non-default, https-only) alongside the existing
  KEK/state-secret checks.
- **Empty destination list** now returns 422 with a clear message
  instead of parking a live user credential in Redis behind an empty
  picker.

### Outstanding review items (not acted on, carried forward)

- **Pre-existing, same bug class as the blocking issue above**: Day 22's
  `x7y8z9a0b1_add_onboarding_status_and_profile_fields.py:25` declares
  `_ONBOARDING_STATUS_VALUES = ("not_started", "in_progress",
  "completed")` — lowercase values against a `SqlEnum(PyEnum)` column
  that binds `NOT_STARTED`. `workspaces.onboarding_status` will reject
  every write on real PostgreSQL. Not fixed here: it belongs to a
  landed migration from another day, and amending an already-applied
  migration is a separate decision. **Should be fixed before any
  PostgreSQL deployment.** Worth auditing every enum migration in the
  repo for the same mismatch at the same time.
- Envelope ciphertext uses no AES-GCM associated data, so a ciphertext
  is portable between rows — someone with database *write* access could
  move connection A's encrypted token onto connection B's row and it
  would decrypt cleanly. Low severity (it presupposes DB write access),
  cheap to harden later by passing `connection_id`/`platform` as AAD.
- `raise_for_platform_error` includes up to 300 chars of the platform's
  response body in its exception message. Contained today — the router
  returns a generic 502 and the service logs only `type(error).__name__`
  — but a future caller logging `str(error)` could surface a payload
  that echoes submitted parameters.
- The adapter layer (`get_adapter`/`_ADAPTERS`) has no production caller
  yet; the service talks to `oauth.get_provider` directly. Expected —
  the adapters exist for Day 24 to consume connections uniformly.

### Testing

46 new tests in `tests/test_platform_connections.py`. Every platform
fixture returns **more than one** destination (3 Facebook Pages, 3
YouTube channels including Brand Accounts, 2 Instagram Business
Accounts), because a single-destination fixture cannot detect "persisted
the first destination returned" — the precise bug this day exists to
prevent. All outbound platform HTTP goes through an `httpx.MockTransport`;
no test reaches the network.

Coverage: state signing/tampering/expiry/cross-profile rejection;
redirect-URI allowlist rejection including the exact-vs-prefix case;
callback returning the full multi-destination list for all three
platforms; Instagram correctly excluding a Page with no linked Business
Account; callback persisting nothing; selection of an id not in the
fetched list rejected; **destination-scoped token stored, not the user
token** (asserted against both the user token and the first-returned
Page's token); YouTube's account-scoped token recorded deliberately;
**two profiles in one workspace selecting two different Pages and ending
up with two independent rows**; reconnect replacing rather than
duplicating; single-use selection token; ciphertext-at-rest in both
Postgres and Redis plus non-determinism and key-id carriage; pending
state expiring from Redis if never finalized; disconnect revoking and
removing, and still removing when revocation fails; refresh success,
failure-to-expired, and no-refresh-token-to-expired; the due query
excluding far-future and NULL-expiry rows; the scheduled job's batch;
unauthenticated 401; cross-workspace 404 across **both** halves of the
ownership chain; selection token not redeemable against another profile;
`__repr__` token safety; and the six review-finding regressions listed
above.

Verification (all actually executed):

- `uv run pytest tests/test_platform_connections.py -q` -> **46 passed**.
- `uv run pytest -q` -> **28 failed, 328 passed**. The baseline captured
  before this day began was **28 failed, 282 passed** — the +46 are
  exactly this day's tests, and the 28 failures are byte-identical by
  name to that baseline (`test_workspaces.py`,
  `test_intelligence_analysis.py`, `test_published_content.py`,
  `test_content_intelligence_synthesis.py`). **No new regressions.**
  Those 28 remain Day 21's outstanding scope, not this day's.
- `uv run ruff check` and `ruff format --check` over all 20 Day 23 files:
  **clean**. Repo-wide, `ruff check .` reports 15 pre-existing errors and
  `ruff format --check .` 25 pre-existing files — identical counts to
  Day 22's record, and **zero** are files this day touched (verified).
  Not fixed: out of scope.
- `uv run alembic heads` -> `y8z9a0b1c2 (head)`, single head.

### Known limitations

- **The Definition of Done's end-to-end sandbox verification against a
  real test account with more than one Page/Channel has NOT been
  performed.** No Meta or Google sandbox credentials are configured in
  this environment (`youtube_oauth_client_id`,
  `facebook_oauth_client_id` etc. are all `None`). Every platform
  interaction is exercised against a mock transport shaped to the real
  API responses. This is the one Definition-of-Done item this day does
  not satisfy, and it is the item specifically intended to catch a
  wrong-destination bug — it must be completed against a real
  multi-destination account before this day is considered fully done.
- The migration has not been run against a real PostgreSQL instance,
  matching the project's existing SQLite convention. The enum-label test
  above compensates for the specific failure mode that convention hid,
  but it is not a substitute for a real migration run.
- **ACTION FOR THE TEAM — start Meta app review now, in parallel.**
  `pages_manage_posts`, `instagram_content_publish`,
  `pages_read_engagement` and `pages_show_list` all require Meta App
  Review before they work for anyone outside the app's own dev/test
  users. That review takes real calendar time that is independent of
  engineering effort and cannot be compressed by finishing the code
  sooner. It should have been started alongside this day's build, not
  after it — Day 24's publish wiring will otherwise be blocked waiting
  on it. YouTube needs its own Google OAuth verification for the
  `youtube.upload` scope, on a similar footing.
- Reusing a prior OAuth grant to skip destination selection when
  connecting a second profile under the same social login is
  deliberately not implemented — each connect attempt re-runs the full
  flow. A known, accepted UX trade-off for this day, not a bug.

## Day 24 - Publishing Foundation with Scheduling (Horizontally-Safe)

> **Numbering note:** `PublishedContent`, its `schedule`/`cancel` flows, and
> a single-table poller were already implemented before this day began,
> committed as "Day 16 — Publishing Foundation" and referred to elsewhere in
> this document (see "Known Limitations" above) as "the Day 17 publish
> scheduler" — a pre-existing numbering inconsistency in the codebase's own
> history, not introduced here. This entry keeps the "Day 24" label the work
> was requested under; it does not attempt to renumber the earlier commit.
> What Day 24 actually adds: real platform publish calls through the Day 23
> adapters, a `publishing` claim state, `platform_post_id`, a stuck-row
> recovery sweep, and — critically — moving due-item promotion off an
> in-process FastAPI-lifespan `asyncio` task and onto a registered Day 15 arq
> periodic job, which is what actually makes the claim-then-call mechanism
> safe to run as more than one instance.

Wires the Day 23 `PlatformConnection`/adapter layer into the existing
publish/schedule flow, replacing the FastAPI-lifespan poller with a Day 15
arq periodic job, and gives immediate and scheduled publishes a real
terminal outcome instead of an always-successful manual placeholder.

- Added `PublishStatus.PUBLISHING`, an intermediate claimed-but-not-yet-
  resolved state between `scheduled` and `published`/`failed`, and
  `platform_post_id` (nullable, only ever set on a genuine adapter success —
  never fabricated, never set for the manual/no-op path).
- `app/platform_connections/adapters.py` gained `publish_content()`: a
  `PublishResult(platform_post_id, external_url)` return contract on the
  `PlatformConnectionAdapter` Protocol. `FacebookAdapter.publish_content`
  makes a real `POST {page_id}/feed` Graph API call against the draft's
  caption/hook/body text and validates the response actually contains a
  post id before treating it as success. `ContentDraft` (Day 12) is
  text-only — there is no video/image asset anywhere in the system — so
  `YouTubeAdapter`/`InstagramAdapter.publish_content` raise a typed
  `MediaRequiredError` before any network call rather than faking a text
  post to a video-only endpoint; this was an explicit, approved scope
  decision, not a stub left unfinished. Every failure mode (no connection,
  expired connection, missing media, a platform HTTP error) resolves to
  `status=failed` with a recorded reason — never an unhandled exception.
- `schedule_draft` now rejects scheduling to youtube/facebook/instagram
  without an active (`status=connected`) `PlatformConnection` for that
  profile/platform (`PlatformNotConnectedError` -> 422). `publish_draft`
  and the scheduled-promotion path both re-fetch the connection fresh,
  immediately before calling the adapter, rather than trusting the
  schedule-time check — a connection revoked or expired between scheduling
  and the due time is caught at call time, not assumed still valid.
- Distributed-safe due-item promotion, two-phase claim-then-call:
  `PublishedContentRepository.claim_publishing` is a single atomic
  `UPDATE published_content SET status='publishing' WHERE status='scheduled'
  AND scheduled_at <= now() RETURNING *`. That one statement is the entire
  correctness guarantee under N concurrent worker instances — only one
  instance's `UPDATE` can match and flip a given row, so a row can never be
  claimed twice regardless of how many workers are polling. The Day 15
  `DistributedLock`/`try_lock` wrapped around the caller
  (`app/services/publish_promotion.py`) is a performance optimization only
  (skips a redundant claim query when another worker already holds the
  tick) — if the lock isn't acquired, that tick simply does nothing, which
  is always safe because the atomic claim doesn't depend on it. Only after
  a row is claimed does the service call the real adapter; there is
  deliberately no auto-retry on failure, since retrying an uncertain
  external call risks a duplicate post — a `failed` row is terminal until
  manual review.
- Recovery sweep (`reclaim_stuck_publishing`, same atomic-`UPDATE`-with-
  `RETURNING` shape): rows stuck in `publishing` past a configurable
  timeout (a worker crashed mid-call after claiming, before resolving) move
  to `failed` for manual review. A concurrent sweep from another instance
  can't double-process the same stuck row either, for the same reason the
  claim itself can't be double-claimed.
- **Replaced the old FastAPI-lifespan `asyncio.create_task` poller
  (`app/services/publish_scheduler.py`, deleted) with two registered Day 15
  arq `cron_jobs`** (`app/workers/settings.py`):
  `promote_due_publishes_cron` (default every 30s, configurable via
  `publish_promotion_interval_seconds`, must evenly divide 60 since arq
  cron fires on second-of-minute marks) and `recover_stuck_publishes_cron`
  (default every 15 minutes). This is the change that actually makes the
  atomic-claim guarantee meaningful: an in-process asyncio task only ever
  runs inside one API process, so it could never have been the thing
  protecting against a double-publish once more than one instance existed.
  `app/main.py` no longer starts anything in-process for publishing; the
  only way `promote_due`/`recover_stuck_publishing` run is via
  `uv run arq app.workers.settings.WorkerSettings`, a separate deployable
  process, matching the Day 15 job-infrastructure convention.
- Fixed a pre-existing bug found while touching this file:
  `PublishedContentService.publish_draft`/`schedule_draft`/
  `cancel_schedule` never called `session.commit()`, so every
  publish/schedule/cancel would flush (visible mid-request) but roll back
  once the request's session closed — nothing ever persisted. Added
  explicit `self.session.commit()` calls, matching the convention every
  other service in the codebase actually follows (each service commits
  itself; there is no shared request-boundary commit layer, despite the
  architecture doc's aspirational framing). `promote_due`/
  `recover_stuck_publishing` deliberately do *not* commit themselves, since
  they run in the arq worker process with no request-scoped session;
  `app/services/publish_promotion.py` opens its own session per job and
  commits once, mirroring the same "commit at the boundary" pattern with
  the arq job as the boundary instead of a FastAPI request.
- Migration `z9a0b1c2d3` (current head): Postgres-safe
  `ALTER TYPE publishstatus ADD VALUE IF NOT EXISTS 'PUBLISHING'` and the
  new `platform_post_id` column; downgrade converts any `PUBLISHING` rows
  to `FAILED` before rebuilding the enum type without the value, following
  the same reversible pattern as `n7o8p9q0r1`.
- Endpoints (`schedule`/`publish-immediately`/`cancel`/`list`/retrieve-with-
  lineage) are unchanged in shape from the pre-existing implementation and
  continue to use Day 21's `require_profile_access` — every ownership
  mismatch is a 404, never 403/400; `get_published_content` additionally
  re-checks `published.profile_id != profile.id` as defense in depth.

### Review

A `backend-reviewer`-persona review (run via a general-purpose agent
carrying that persona, since the project's custom `backend-reviewer`
subagent type is not invocable as a distinct `subagent_type` in this
environment) found **no Blocking (CRITICAL/HIGH) issues**. Two non-blocking
items were logged and left as-is:

- **[MEDIUM, test-honesty only, not a production defect]** The two
  "concurrent worker" tests in `tests/test_published_content.py` run two
  `PublishedContentService` instances against the *same* shared SQLite
  session/connection (per the project's existing `db_session` test
  fixture), so they prove the claim is self-consistent under sequential
  reinvocation, not genuine two-connection concurrency — SQLite can't
  exercise that regardless. The production claim mechanism itself
  (`UPDATE ... RETURNING`) is correct and Postgres-safe by construction;
  only the test docstrings slightly overstate what they demonstrate.
  Matches the project's existing, already-documented SQLite-vs-Postgres
  testing-gap convention (see Day 13/19/23's own notes) rather than being a
  new gap.
- **[LOW, pre-existing, not a Day 24 regression]** `PublishedContent.draft`
  uses `lazy="selectin"` unconditionally, so list/create/cancel responses
  (none of which expose draft fields) still eager-load the related
  `ContentDraft` on every call. Present since the original Day 16
  publishing-foundation commit; not touched here.

### Verification (all actually executed)

- `uv run pytest tests/test_published_content.py -q` -> **26 passed**
  (includes the retrofitted Day 21 auth this file was missing, and 13 new
  Day 24 tests: schedule/publish/cancel flows, the named
  atomic-claim-alone-with-the-lock-removed test, adapter success/failure
  paths, publish-against-a-disconnected-connection rejection, the stuck-
  publishing recovery sweep, index usage, and ownership isolation).
- `uv run pytest tests/test_platform_connections.py -q` -> **46 passed**,
  no regression from the `adapters.py` additions.
- `uv run pytest -q` (full suite) -> **14 failed, 354 passed**. The Day 23
  baseline was 28 failed, 328 passed, with `test_published_content.py`
  explicitly listed among the pre-existing failures (it had never been
  retrofitted with Day 21 auth). The 14 remaining failures are
  byte-identical by name to the non-`test_published_content.py` subset of
  that baseline (`test_workspaces.py`, `test_intelligence_analysis.py`,
  `test_content_intelligence_synthesis.py`) — Day 21's outstanding scope,
  untouched by this day. **No new regressions**; this day's auth retrofit
  incidentally closed the `test_published_content.py` gap as a side effect.
- `uv run ruff check` and `uv run ruff format --check` over every Day 24
  file: **clean** (one real formatting fix applied to
  `app/services/published_content.py` during this day's own testing pass).
  Repo-wide `ruff check .` still reports pre-existing errors in
  `app/models/content_evaluation.py`, `app/repositories/content_evaluation.py`,
  `app/schemas/content_evaluation.py`, `app/services/evaluation/evaluator.py`,
  `app/services/evaluation/scoring.py`, `app/services/persona.py`, and the
  `l5m6n7o8p9` migration — none touched by this day, not fixed, out of
  scope.
- `uv run alembic heads` -> `z9a0b1c2d3 (head)`, single head.

### Known limitations

- The Definition of Done's concurrent-worker claim test does not exercise
  genuine multi-connection concurrency under SQLite (see Review above) —
  a real-Postgres verification of the atomic claim under actual concurrent
  transactions has not been performed, matching the project's existing
  SQLite-vs-Postgres testing convention rather than being a new gap.
- YouTube and Instagram publishing remain a deterministic `MediaRequiredError`
  failure, not a working integration — `ContentDraft` has no video/image
  asset to publish. This is an explicit, approved scope decision for this
  day, not unfinished work; building a media-asset pipeline is out of scope
  here and not yet scheduled.
- Retracting an already-published item, and any automatic retry of a
  failed publish, remain explicitly out of scope (unchanged from the prior
  "Known Limitations" note above, now narrowed: only retraction and retry
  remain open — real publishing API calls and job-queue-routed promotion,
  both previously listed there, are done as of this day).

## Day 25 - Performance Ingestion Pipeline

Attaches recorded metrics to a specific `PublishedContent` record and runs
the existing Day 9 `PerformanceAnalysis` logic against that
lineage-connected data as a Day 15 async job, instead of the Day 9
profile-scoped-only, synchronous-only entry points.

- `ContentPerformance` gained `published_content_id` (FK to
  `published_content.id`, `ondelete="CASCADE"`, nullable — pre-Day-25
  profile-scoped records never had one, and the new manual entry endpoint
  always sets it) and `reporting_period` (`Date`, nullable). A
  `UniqueConstraint("published_content_id", "reporting_period")` enforces
  duplicate-period rejection at the database level rather than an
  application-level pre-check, so a genuine concurrent double-submission for
  the same published item/period can't race past a check-then-insert gap;
  NULL `published_content_id` values never collide under it in either
  SQLite or PostgreSQL. A composite `Index("profile_id",
  "published_content_id")` supports the baseline-comparison join as history
  grows.
- `POST /profiles/{profile_id}/published/{published_id}/metrics`: manual
  metrics-entry endpoint accepting
  views/likes/comments/shares/saves/reach/watch_time_seconds/retention_rate
  plus a required `reporting_period`. Ownership is validated through the
  full workspace -> profile -> `PublishedContent` chain (`require_profile_access`
  plus a profile-scoped `PublishedContentRepository.get_by_id` lookup) —
  any mismatch is a 404, matching the Day 21 convention. The record insert
  and the duplicate-period `IntegrityError` -> `DuplicateReportingPeriodError`
  -> `409 CONFLICT` translation happen inline; the Day 9 analysis itself
  does not — the endpoint enqueues a Day 15 `performance_analysis` job via
  `submit_job` and returns `202 ACCEPTED` with `content_performance_id` and
  `job_id` immediately.
- The pre-existing manual `/performance/{id}/analyze` endpoint is converted
  from an inline call into the same `submit_job` path
  (`ContentPerformanceService.enqueue_analysis`), so both entry points now
  share one asynchronous invocation pattern. `ContentPerformanceService.analyze()`
  itself — the Day 9 baseline-comparison and classification logic — is
  byte-for-byte unchanged; only how it gets invoked changes.
- Job handler (`_run_performance_analysis_job`, registered against
  `performance_analysis` in `app/infrastructure/jobs/registry.py`, imported
  at worker startup via `app/workers/settings.py`) calls
  `PerformanceInsightService.create()`, which runs the unchanged Day 9
  `analyze()` first and commits it, then attempts the Day 16-style
  AI-reasoned `PerformanceInsight` on top. Per the "deterministic first, AI
  enriched" rule, an `AIError` (all providers unavailable) does not fail the
  job or lose the analysis — the deterministic `PerformanceAnalysis` already
  committed survives regardless of insight generation's outcome.
- Migration `b7c8d9e0f1a2` (new head, `Revises: z9a0b1c2d3`): adds the two
  columns, the FK, the unique constraint, and both indexes; fully
  reversible. (Originally authored as `a1b2c3d4e5f6`, which collided with
  the pre-existing `a1b2c3d4e5f6_create_business_domain.py` revision id from
  Day 6 — renumbered to `b7c8d9e0f1a2` here so `alembic heads` resolves to a
  single head instead of erroring on a duplicate revision.)
- Out of scope, per the day's spec: live polling of social platform APIs
  (metrics are still caller-submitted, matching Day 9's existing "no
  external OAuth flow or social API integration" boundary for this domain),
  the Learning Engine (Day 26), and any change to Day 9's scoring/
  classification formulas.

### Testing

- `uv run pytest tests/test_performance.py -v` -> **7 passed**: existing
  Day 9 CRUD/median-analysis and workspace-isolation coverage, plus five new
  Day 25 tests — ownership rejection (404) for unowned `PublishedContent`,
  successful submission enqueueing a job, duplicate-period conflict (409),
  a genuine concurrent duplicate-period race resolving to exactly one
  success (via a new `db_session_factory` test fixture backed by a
  `StaticPool`-shared SQLite in-memory engine, since the default
  single-session fixture can't exercise a real two-connection race), and
  baseline comparison against real `PublishedContent` history.
  `tests/conftest.py` and the `create_opportunity` helper in
  `tests/test_content_briefs.py` (which the concurrency test's fixtures
  share) were adjusted in support of this — the former to add the shared
  session factory, the latter to reuse an existing `MarketIntelligence`
  record instead of creating a duplicate one per call, fixing a pre-existing
  test-isolation bug the new test path exposed.
- `uv run pytest -q` (full suite) -> **14 failed, 359 passed**, byte-identical
  by name to the pre-existing baseline documented in Day 24's own entry
  (`test_workspaces.py`, `test_intelligence_analysis.py`,
  `test_content_intelligence_synthesis.py` — Day 21's outstanding scope).
  No new regressions from this day's changes.
- `uv run ruff check` / `uv run ruff format --check` over every Day 25 file
  (model, service, schema, router, migration, the three test files): clean.
  Repo-wide `ruff check .` still reports the same pre-existing, untouched
  errors noted in Day 24's entry, plus similar drift in
  `app/services/persona.py` and the `l5m6n7o8p9` migration — none touched
  by this day.
- `uv run alembic heads` -> `b7c8d9e0f1a2 (head)`, single head, after the
  revision-id rename above.
- `uv run alembic check` could not be run against a live PostgreSQL
  instance in this environment (no reachable Postgres server) — matches the
  project's existing, already-documented SQLite-vs-Postgres testing-gap
  convention rather than a new gap. The migration was instead verified by
  direct read-through against the model's column/constraint/index
  definitions.

### Known limitations

- Metrics entry remains manual/caller-submitted; there is no live polling
  or scheduled pull from platform APIs, matching Day 9's original scope
  boundary and this day's explicit out-of-scope list.
- The unique-constraint concurrency test exercises a real SQLite
  `StaticPool`-shared two-session race rather than genuine PostgreSQL
  multi-connection concurrency — a real-Postgres verification has not been
  performed, matching the project's existing SQLite-vs-Postgres testing
  convention (see Day 13/19/23/24's own notes) rather than being a new gap.
- `PerformanceInsight` generation from the async job path depends on the
  same AI provider availability as the pre-existing Day 16 insight flow; no
  new fallback behavior was added beyond the existing deterministic-first
  guarantee.

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
`database_url` is a `postgresql` URL.

As of the Neon migration (see "Database Migration: PostgreSQL → Neon"
below), the app connects through Neon's PgBouncer pooler rather than
directly to Postgres, which changes the sizing question. PgBouncer already
multiplexes connections server-side across every app process/instance, so
the SQLAlchemy pool is no longer bounded by a shared `max_connections`
figure the way the original (pre-Neon) formula assumed:

```text
(pre-Neon) (app instances) x (db_pool_size + db_max_overflow) <= postgres max_connections - headroom
```

Instead, the SQLAlchemy pool only needs to be large enough that a single
app process doesn't queue checkouts under its own realistic concurrency —
PgBouncer's own pool size on the Neon side (not configured by this app) is
what actually bounds backend Postgres connections. Current defaults are
`db_pool_size=5`, `db_max_overflow=5` (10 concurrent checkouts per
process), comfortably above this API's per-process concurrency at this
stage. Re-derive if a deployment tier's real concurrency demands it.

Statement timeout: `db_statement_timeout_ms` (default 30000ms), set via
asyncpg `connect_args={"server_settings": {"statement_timeout": "..."}}`
at connection time. This is a query-execution timeout, not a connection
-acquisition timeout — it is unrelated to Neon's autosuspend cold-start
latency (the delay before a suspended branch's compute wakes up), which
only affects how long *acquiring* a new connection takes.

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

- ~~The Day 17 publish scheduler still deliberately remains its own narrow
  single-table poller rather than routing through the Day 15 job queue.~~
  Resolved by Day 24: due-item promotion is now a registered Day 15 arq
  `cron_jobs` entry, not an in-process poller.
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
  an already-published item, remain out of scope (Day 24 wired real publish
  calls and distributed-safe promotion, but deliberately did not add
  retry or retraction).
- ~~Real publishing API calls for any platform~~ — resolved by Day 24 for
  Facebook (real Graph API `feed` post). YouTube and Instagram deliberately
  raise `MediaRequiredError` rather than a working integration, since
  `ContentDraft` has no video/image asset (see Day 24's own notes). TikTok,
  LinkedIn and X still have no OAuth implementation at all.
- Performance metrics ingestion from published content.
- A learning-alignment scoring factor for `ContentOpportunity` (explicitly
  out of scope for Day 18 — a scoring-formula change, distinct from Day 18's
  rationale-only change).
- Re-triggering `opportunity_reasoning` when an opportunity's
  `target_objective` changes via `PATCH` (Day 18 only reasons at creation).
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
CRITICAL GAP" note); that retrofit is Day 21. Day 22 adds the first signup
path and a step-wise, resumable onboarding flow. Day 23 adds the system's
first real external-platform integration: OAuth 2.0 connect/disconnect for
YouTube, Facebook and Instagram, built around the rule that one OAuth login
is not one publishable destination — a mandatory destination-selection step
sits between token exchange and persistence, so two ContentProfiles in the
same workspace can hold independent connections to different Pages/Channels
through the same social login. Credentials are envelope-encrypted at rest in
both Postgres and the short-TTL Redis pending state, a scheduled job
refreshes near-expiry tokens and marks failures `expired` rather than
failing silently at publish time, and the Day 9 adapter contract gains real
YouTube/Facebook/Instagram implementations of its connection/authorization
surface only. Day 24 wires those connections into the pre-existing
publish/schedule flow: a real Graph API publish call for Facebook,
a deterministic fail-fast (`MediaRequiredError`) for YouTube/Instagram since
`ContentDraft` has no video/image asset, and — the day's core safety
change — due-item promotion moved from an in-process FastAPI-lifespan
poller to a registered Day 15 arq periodic job built on the same atomic
claim-then-call `UPDATE ... RETURNING` guarantee, now actually meaningful
once more than one API/worker instance exists. No TikTok/LinkedIn/X, no new
job/queue system, no retry-on-failure logic, no advanced media generation,
autonomous strategy features, learning-alignment scoring, draft editing
changes, or performance/metrics ingestion were added. Day 25 adds that
performance/metrics ingestion: a manual metrics-entry endpoint attaches a
caller-submitted snapshot to a specific `PublishedContent` record and
enqueues the existing Day 9 `PerformanceAnalysis` logic as a Day 15 async
job rather than running it inline, with database-level duplicate-period
rejection and full workspace/profile/`PublishedContent` ownership
validation. No live platform polling, Learning Engine work (Day 26), or
change to Day 9's scoring/classification formulas was added.

## Day 26 - Learning Engine v1 + Intelligence Feedback Loop Closure

Closes the Learning Loop (product-architecture.md's Principle 12, "Learning
Must Feed Strategy"): durable strategic patterns are now extracted from
accumulated Day 9/25 `PerformanceAnalysis` history into a new `Learning`
entity, and active learnings feed back into the deterministic
`opportunity_scorer` as a small, capped, additive factor -- the first case of
Performance Intelligence actually influencing a future opportunity's score
rather than only being displayed.

- `Learning` model (`app/models/learning.py`): `profile_id`, `dimension`
  (`format | topic | pillar | hook_style | cta | timing`), `dimension_value`,
  `pattern_description` and `confidence_level` (always deterministic --
  extraction-job-owned, never client-writable), `explanation` (AI-enriched or
  deterministic, tracked via `explanation_generation_source`),
  `supporting_evidence` (JSONB: the `PerformanceAnalysis` ids and sample
  stats the pattern was computed from), and `status`
  (`active | superseded` -- a simple flag; automatic supersession is out of
  scope). A `UniqueConstraint(profile_id, dimension, dimension_value)` makes
  the extraction job's upsert idempotent, and a composite
  `Index(profile_id, status, dimension)` gives the opportunity scorer's
  per-opportunity lookup a cheap indexed read rather than a scan, per the
  day's system-design requirement. Migration `c8d9e0f1a2b3` (new single
  head).
- Extraction (`app/learning/extraction.py`,
  `extract_learnings_for_profile`): a **read-only consumer** of
  `ContentPerformanceRepository` -- it never writes to
  `ContentPerformance`/`PerformanceAnalysis` -- that compares each profile's
  per-`format`/per-`topic` average `relative_engagement` (Day 9/25's
  baseline-comparison output) against the profile's overall average. Only
  `format` and `topic` are extracted in v1, since those are the only
  `LearningDimension` values with real structured backing data on
  `ContentPerformance` today; `pillar`/`hook_style`/`cta`/`timing` remain
  valid for manually-created or future learnings. A candidate is surfaced
  only once a profile has at least `learning_extraction_min_analyses`
  (default 6) analyzed records overall, a dimension value has at least
  `learning_extraction_min_group_size` (default 3) records, and its relative
  delta clears `learning_extraction_min_delta_threshold` (default 20%) --
  all three configurable per deployment in `app/core/config.py`. Runs as a
  registered Day 15 arq **cron** job (`extract_learnings_cron`, nightly at
  `learning_extraction_hour`/`learning_extraction_minute`, default 3:00 AM),
  never per-metrics-submission, guarded by a `try_lock` against redundant
  concurrent runs across worker instances -- correctness itself comes from
  the model's unique constraint, so re-running the job for the same period
  upserts rather than duplicates. A `learning_explanation` AI task
  (`LearningExplainer`) enriches only the `explanation` text from the
  deterministic pattern/evidence; on `AIError` the explanation falls back to
  the deterministic `pattern_description` and
  `explanation_generation_source` records `deterministic`, per Principle 16.
- CRUD/list API (`app/api/v1/learnings.py`, under
  `/profiles/{profile_id}/learnings`): standard workspace-ownership-chain
  enforcement via `require_profile_access` (404 on any mismatch, matching
  Day 21). `LearningUpdate` only accepts `status` -- pattern data,
  confidence, and evidence stay extraction-job-owned and are never
  client-writable, matching the schema-layer stripping rule this file's
  CLAUDE.md documents for other server-controlled fields.
- **Feedback loop closure** (`app/ai/strategy/opportunity_scorer.py`):
  extended `OpportunityScorer.score()` with a `learning_alignment` factor,
  computed by `calculate_learning_alignment` / `find_matching_learning` --
  matches a new opportunity's recommended format or signal topic against
  active (`LearningStatus.ACTIVE`) learnings on the `format`/`topic`
  dimensions, and takes the highest-confidence match. The adjustment is
  `confidence_level * LEARNING_ALIGNMENT_WEIGHT` (weight = **0.05**,
  documented alongside the constant), applied **additively on top of** --
  never rebalanced into -- the four existing weighted factors
  (`signal_strength` 0.30, `profile_relevance` 0.30, `goal_alignment` 0.20,
  `timeliness` 0.20), so it can nudge a score by at most 0.05 and never
  dominates it. It defaults to `0.0` whenever no learnings are supplied or
  none match, which is byte-identical to pre-Day-26 scoring behavior for
  every profile with zero active learnings.
  `ContentOpportunityService.create()` (`app/services/content_opportunity.py`)
  queries `LearningRepository.list_active_for_dimensions` (the indexed
  read) and passes the result into `scorer.score()`; the matched
  `Learning`'s id is recorded on `opportunity_metadata.influencing_learning_id`
  alongside the existing `score_components`.
- `strategic_rationale` (`app/services/opportunity_reasoning.py`,
  `generate_rationale`) now looks up `influencing_learning_id` from that
  metadata when present, re-validates it against the opportunity's own
  `profile_id`, and passes the learning's `dimension`/`dimension_value`/
  `pattern_description`/`explanation` into the `opportunity_reasoning` AI
  task's context as `influencing_learning`, so the LLM-reasoned rationale
  can explicitly cite the pattern as evidence rather than only ever
  grounding in the cross-domain intelligence synthesis.
- Out of scope, per the day's spec: automatic learning supersession beyond
  the `active`/`superseded` status flag, and any change to
  Brief/Draft/Variation/Evaluation scoring.

### Testing

- `uv run pytest tests/test_learning.py -v` -> **10 passed**: scorer
  baseline regression (`learning_alignment` defaults to `0.0` and `total` is
  unchanged with no active learnings supplied), a capped-bonus case on a
  format match, superseded learnings ignored by the matcher, extraction
  surfacing a clearly-separated high-performing format and re-running
  idempotently (no duplicate rows), a below-minimum-analyses profile
  correctly skipped, AI-enriched vs. deterministic-fallback explanation
  generation, full CRUD/list, cross-tenant 404 ownership isolation, and an
  end-to-end integration test confirming an active learning both raises a
  new opportunity's score/metadata and reaches the `opportunity_reasoning`
  AI context verbatim.

## Database Migration: PostgreSQL → Neon

Local dev and the test suite now target Neon (serverless Postgres, fronted
by PgBouncer in transaction-pooling mode) instead of a self-managed
Postgres instance. No Docker is involved (none was used before this
change either). Scope is local dev/test only — no CI pipeline exists yet
to update.

### What changed

- `Settings` (`app/core/config.py`) gained three new fields alongside the
  existing `database_url`: `database_url_direct`, `test_database_url`,
  `test_database_url_direct` — see `.env.example` for what each points at.
- `app/core/database.py`'s engine `connect_args` now sets `ssl="require"`
  (asyncpg needs this kwarg explicitly — Neon's `?sslmode=require` query
  string is not honored by SQLAlchemy's asyncpg dialect) and
  `statement_cache_size=0` (disables asyncpg's client-side prepared
  -statement cache, the one real hazard under PgBouncer transaction
  pooling — no advisory locks, `LISTEN`/`NOTIFY`, or explicit `PREPARE`
  exist anywhere in this codebase).
- `migrations/env.py` now runs all Alembic DDL against `database_url_direct`
  instead of the pooled `database_url` — PgBouncer transaction-pooling mode
  doesn't reliably support the session semantics Alembic needs.
- `tests/conftest.py` no longer spins up an in-memory SQLite database per
  test. It runs `alembic upgrade head` once per test session against
  `test_database_url_direct`, then gives each test an isolated view of the
  persistent `test` branch via SQLAlchemy's "join into an external
  transaction" pattern: one connection, one outer transaction per test,
  sessions bound to it with `join_transaction_mode="create_savepoint"`.
  Application-level `commit()` calls only release a SAVEPOINT; the outer
  transaction is rolled back at teardown, so nothing a test writes is ever
  visible outside it and no truncate/reset step is needed between runs.
  `test_concurrent_duplicate_reporting_period_exactly_one_succeeds`
  (`tests/test_performance.py`) is the one deliberate exception: it needs
  two genuinely independent, really-committing connections for its race
  against a real unique constraint to mean anything, so it opens real
  sessions directly against the pooled test engine and cleans up its own
  rows in a `finally` block instead of relying on the standard rollback.

### Two Neon branches: `dev` and `test`

- **`dev`** — what the locally running API (`uvicorn`) and worker (`arq`)
  connect to via `DATABASE_URL`/`DATABASE_URL_DIRECT`.
- **`test`** — used only by the automated test suite via
  `TEST_DATABASE_URL`/`TEST_DATABASE_URL_DIRECT`, isolated from `dev` so
  running the suite can never touch/wipe whatever a developer is looking
  at locally.

Both branches were created empty — no existing dev data was migrated —
and `alembic upgrade head` was run against both from scratch as the
initial clean-slate verification.

### Pooled vs. direct connections

Every branch exposes two endpoints: a pooled one (host has a `-pooler`
suffix, routed through PgBouncer in transaction-pooling mode) and a direct
one (unpooled). The app and test suite always connect through the pooled
endpoint at runtime; only Alembic (and the test suite's one-time schema
migration) uses the direct endpoint, since DDL needs real session
semantics that transaction pooling doesn't guarantee.

### Revised connection pool sizing

See "Database connection pool sizing" under Platform Infrastructure above
for the full reasoning — in short, PgBouncer now absorbs connection fan-in
across app processes server-side, so the SQLAlchemy pool no longer needs
to be sized against a shared Postgres `max_connections` ceiling; it only
needs to avoid queueing within a single process. Defaults moved from
`db_pool_size=10`/`db_max_overflow=5` to `db_pool_size=5`/
`db_max_overflow=5`.
