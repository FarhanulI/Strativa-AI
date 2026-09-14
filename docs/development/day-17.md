## 7. Day 17 (Content Intelligence Synthesis Engine)

> **Numbering note:** This section is also numbered "Day 17," duplicating the
> Publishing Foundation work above. The two pieces of work were scoped and
> executed independently under the same day number; per the project's
> established practice for this situation (see `docs/development/progress.md`'s
> "Day 16 (Intelligence Reasoning Layer)" numbering note), this section keeps
> the Day 17 label and Section 1-6 above are left as-is pending a later
> renumbering pass by the project owner. Treat both halves of this document as
> real, completed work until that reconciliation happens.

### 7.1 Goal

Implement `strategic_synthesis`: the first module that reads across all four
Content Intelligence domains — Brand, Audience, and Market analysis (Day 16's
Intelligence Reasoning Layer) and Performance Intelligence (Day 9) — and
combines whichever of them currently exist for a profile into one grounded
cross-domain strategic summary. This is the architecture's "central brain"
concept (`docs/product/product-architecture.md`, "Content Intelligence is the
Central Brain") given its first real implementation: previously each domain's
LLM reasoning stood alone, with nothing synthesizing them into a single
picture for downstream strategy work.

### 7.2 Ownership

- **Owns**: `ContentIntelligenceSynthesis` lifecycle and the `strategic_synthesis`
  AI task/job handler.
- **Consumes**: `BrandAnalysis` / `AudienceAnalysis` / `MarketAnalysis` (Day 16,
  read-only) and `PerformanceInsight` (Day 9, read-only) — synthesis never
  mutates a component analysis or insight.
- **Does not own**: Opportunity scoring or rationale. Feeding synthesis into
  `app/ai/strategy/opportunity_scorer.py` or `opportunity_reasoning` is
  explicitly Day 18 — this day only produces the grounding artifact.

### 7.3 What Was Built

- New `app/content_intelligence/` domain module — the first module organized
  around reading across domains rather than living inside one of them:
  - `grounding.py` — `gather_synthesis_grounding` queries the current
    `BrandAnalysis`/`AudienceAnalysis`/`MarketAnalysis` row per domain (via the
    existing `IntelligenceAnalysisRepository`) and the profile's most recent
    active `PerformanceInsight` rows (limit 5). A domain only counts as
    "available" if its current analysis exists **and** its
    `generation_source` is `ai` or `ai_fallback` — an `insufficient_data`
    analysis carries only a templated placeholder message, not real
    reasoning, so it is deliberately excluded from the count. Returns the
    deterministic `supporting_analyses` id list (real `BrandAnalysis`/
    `AudienceAnalysis`/`MarketAnalysis`/`PerformanceInsight` ids only, never
    anything from an LLM response), the per-domain context payload, and a
    templated fallback summary for the insufficient-data/AI-fallback paths.
  - `reasoner.py` — `SynthesisReasoner`, mirroring
    `app.services.llm.intelligence_reasoner.IntelligenceReasoner`'s shape,
    calls the AI Router with `AITask.STRATEGIC_SYNTHESIS` and
    `required_capabilities={REASONING, STRUCTURED_OUTPUT, LONG_CONTEXT}` —
    the first task in the codebase to actually declare capability
    requirements on the request, per the architecture's "a `strategic_synthesis`
    task requires a reasoning-capable model with structured output and long
    context" example.
  - `service.py` — `generate_synthesis` (the job-handler-only reasoning path,
    mirroring `app.services.intelligence_analysis.generate`),
    `ContentIntelligenceSynthesisService.get_or_enqueue` (the read path,
    mirroring `IntelligenceAnalysisService`), and
    `mark_synthesis_stale_and_invalidate` (see 7.5).
- `ContentIntelligenceSynthesis` model (`app/models/content_intelligence_synthesis.py`):
  `profile_id`, `summary`, `key_themes` (JSONB list of strings),
  `supporting_analyses` (JSONB list of real component-analysis/insight ids),
  `generation_source` (reuses Day 16's `AnalysisGenerationSource` enum —
  `ai` | `ai_fallback` | `insufficient_data` — rather than duplicating it),
  `is_current`, `is_stale`, `synthesis_version`, `generated_at`. A partial
  unique index (`postgresql_where`/`sqlite_where is_current`) enforces exactly
  one `is_current=true` row per profile at the database level — closing the
  gap Day 16 explicitly left open (Day 16 only maintained "one current row"
  by transaction ordering, with no DB constraint).
- Deterministic fallback: fewer than two available component domains (by the
  "available" definition above) short-circuits to
  `generation_source=insufficient_data` with a templated message listing
  which domains are present/missing — no AI call is made. Two or more
  available domains calls the AI Router; on success `generation_source=ai`
  with the model's `summary`/`key_themes`; on any `AIError`,
  `generation_source=ai_fallback` with a templated summary built from the
  available domain names — never a fabricated interpretation.
- Staleness-driven invalidation: `mark_synthesis_stale_and_invalidate` is
  called from two existing call sites on successful regeneration —
  `app.services.intelligence_analysis.generate()` (Brand/Audience/Market) and
  `app.services.performance_insight.PerformanceInsightService.create()`
  (Performance) — using the caller's already-verified `profile`/`workspace_id`.
  It only flips `is_stale=True` on the profile's current synthesis row and
  drops its cache entry; it does **not** eagerly regenerate, so several
  components changing close together cannot trigger a thundering herd of
  synthesis jobs. Regeneration happens lazily, the next time the GET endpoint
  is called.
- `strategic_synthesis` AI task registered in `TASK_PROVIDER_POLICY`
  alongside the Day 16 domain tasks, and run through the Day 15 `ai_jobs`
  queue exactly like Day 16 — never synchronously inside a request.
  `app/workers/settings.py` now also imports `app.content_intelligence.service`
  so the arq worker process registers the `strategic_synthesis` handler.
- `GET /api/v1/profiles/{profile_id}/synthesis`: returns the current
  synthesis (200) if one exists and its `is_stale` flag is `False`;
  otherwise enqueues a regeneration job (or reuses an already
  `queued`/`running` job for the same profile, reusing the exact in-flight-job
  dedup pattern from Day 16) and returns `202` with a pending-job status
  body — the endpoint never blocks on the AI call. Cached at
  `profile:{profile_id}:synthesis:workspace:{workspace_id}` (namespaced by
  `workspace_id` for the same reason as Day 16's analysis cache key — a
  cache hit must never bypass the ownership check) with
  `cache_synthesis_ttl_seconds` (default 1800s, six times the Day 16 domain
  analysis TTL), since this is the most expensive reasoning call in the
  system per the day's design goal.
- Historical synthesis rows are kept — `is_current` moves to the newest row
  on regeneration rather than overwriting the previous one — per the
  architecture's data-lineage principle.
- Migration `q0r1s2t3u4` creates the `content_intelligence_synthesis` table,
  reusing the existing `analysisgenerationsource` Postgres enum from Day 16's
  `p9q0r1s2t3` migration (`create_type=False`) rather than creating a
  duplicate enum type, plus the partial unique index and standard
  profile/generated_at/is_current/is_stale indexes. Reversible.

### 7.3.1 Cold-Start / Activation Mode (amendment, 2026-09-14)

Patched after initial implementation. The original fallback logic treated
"fewer than two available component analyses" as one undifferentiated
`insufficient_data` case, which incorrectly penalized brand-new creator
profiles once Day 16's stated-data grounding amendment (see
`docs/development/day-16.md`) let Brand, Audience, and Market analysis all
generate immediately after onboarding — Performance Intelligence is the
only domain legitimately unavailable for a profile that hasn't published
anything yet, and that absence is expected, not a data gap.

`gather_synthesis_grounding` (`app/content_intelligence/grounding.py`) now
distinguishes two different reasons Performance can be absent from the four
inputs:

1. **Genuine insufficient data** — Brand, Audience, or Market analysis is
   also thin or missing. Unchanged: `generation_source=insufficient_data`,
   no AI call made.
2. **Cold start** — Brand, Audience, and Market analyses are all present
   and adequately grounded (`{"brand", "audience", "market"}` is a subset
   of `available_domains`), and Performance is absent. This is verified
   directly by counting the profile's `PublishedContent` and
   `ContentPerformance` rows — both must be zero — never inferred from
   Performance analysis being null alone, since a profile could also be
   missing Performance analysis for other reasons (published content with
   no `PerformanceInsight` generated yet, which is a real gap, not cold
   start).

Cold start does not change the `sufficient` threshold (three domains
already satisfies `component_count >= 2`), but it does change how
generation runs: `SynthesisReasoner.reason()` takes a `cold_start` bool and,
when true, appends `COLD_START_PROMPT_ADDENDUM` to the system prompt —
framing the absence of performance history as expected rather than a
limitation, asking for an opportunity/activation-focused summary of what a
strong first piece of content should be (grounded only in Brand/Audience/
Market), and explicitly forbidding fabricating or implying performance data
that doesn't exist. `generate_synthesis` always runs the full AI call in
this case — cold start never short-circuits to a deterministic fallback the
way genuine insufficient data does.

A new `cold_start` boolean column on `ContentIntelligenceSynthesis` records
which case produced the row (`False` for both genuine-insufficient-data and
ordinary warm-profile rows). `is_stale`/lazy-regeneration behavior is
unchanged: once a profile publishes its first content (a `PerformanceInsight`
becomes available), the existing staleness mechanism naturally triggers
regeneration that produces `cold_start=False` with Performance included.

Day 18's `opportunity_reasoning` already consumes `ContentIntelligenceSynthesis`
and will pick up `cold_start` automatically once this column exists — Day
18's code itself was not modified by this amendment.

### 7.4 Explicitly Out of Scope (confirmed not built)

- Feeding synthesis into `ContentOpportunity` scoring or
  `opportunity_reasoning` — Day 18.
- Exposing synthesis as a standalone user-facing feature — it is an internal
  grounding artifact for downstream reasoning only, per the day's scope.
- Any change to Brand/Audience/Market analysis (Day 16) or Performance
  Intelligence (Day 9) generation logic itself, beyond the new
  staleness-marking call.

### 7.5 Security

Identical ownership chain to every other domain: `ContentIntelligenceSynthesisService
.get_or_enqueue` validates the profile through `ContentProfileRepository
.get_by_id(profile_id, workspace_id)` before touching the synthesis table, and
any mismatch returns `404`, whether reading or triggering regeneration.
`mark_synthesis_stale_and_invalidate`'s `workspace_id` argument is always
sourced from a value the caller already verified — `profile.workspace_id`
freshly loaded from the DB in `generate()`, and the `workspace_id` a caller
already passed a successful `ContentProfileRepository.get_by_id` check with
in `PerformanceInsightService.create()` — so it can't corrupt another
tenant's cache key or invalidate another profile's synthesis.

### 7.6 Testing

`tests/test_content_intelligence_synthesis.py` (12 tests): grounded synthesis
across all four inputs asserting `supporting_analyses` contains only real ids
(brand + audience + market analysis ids plus a performance insight id),
insufficient-data fallback with 0 and 1 available components, AI-provider
failure fallback, staleness triggered by a Brand analysis regeneration,
staleness triggered by a new Performance insight (through the real
`PerformanceInsightService.create` call, not a direct DB write), regeneration
preserving history (`is_current` moves, old row persists), the GET endpoint's
enqueue-then-serve-fresh-then-serve-from-cache round trip through a real
`execute_ai_job` call, job-success cache invalidation, stale-marking cache
invalidation, workspace/profile ownership isolation (404), and the service's
`get_or_enqueue` returning the current row without enqueuing when it isn't
stale.

**Cold-Start / Activation Mode amendment testing** (added 2026-09-14, same
file): `test_cold_start_synthesis_runs_as_full_ai_generation` seeds Brand,
Audience, and Market analysis with zero `PublishedContent`/
`ContentPerformance` and asserts `generation_source=ai` (not
`insufficient_data`), `cold_start=True`, `supporting_analyses` has exactly
3 entries, the summary reads as an activation/first-content
recommendation (keyword check, not an exact-string match), and the system
prompt actually sent to the AI Router contains the cold-start framing
addendum. `test_cold_start_becomes_false_after_first_publish` regenerates
the same profile's synthesis after seeding its first
`PerformanceInsight` and asserts `cold_start` flips to `False` with all 4
domains now in `supporting_analyses`.
`test_insufficient_data_fallback_with_fewer_than_two_components` (existing,
extended) now also asserts `cold_start is False` for the genuine
-insufficient-data case, confirming cold start and insufficient data can
never both be true for the same row.

Fixing this feature surfaced one required change to existing Day 16 tests:
`tests/test_intelligence_analysis.py`'s autouse Redis-fake fixture patched
`get_redis` only in `app.api.v1.intelligence_analysis` and
`app.services.intelligence_analysis` — once `generate()` started calling
`mark_synthesis_stale_and_invalidate` (which also calls `get_redis()`, now
from `app.content_intelligence.service`), those tests attempted a real Redis
connection and failed. Fixed by adding the same patch target to that
fixture; this is not a design gap, just an existing test fixture that needed
to grow one more monkeypatch line for a new internal collaborator.

Verification completed with:

- 12 new tests in `tests/test_content_intelligence_synthesis.py`, all passing.
- Full repository regression suite passing: 266 tests (252 pre-existing +
  12 new + 2 additional from the `tests/test_intelligence_analysis.py` fixture
  fix's parametrization not changing count — see above).
- Ruff check and format check clean for all Day 17 (Synthesis) files.
- Migration chain validated with a single head (`q0r1s2t3u4`).
- An independent architecture review (mirroring the Day 16 backend-review
  pass) specifically checked for a repeat of Day 16's cache-key-ownership
  bypass class of bug, cross-tenant `workspace_id` corruption in the
  staleness/cache-invalidation path, LLM-fabricated lineage leaking into
  `supporting_analyses`, and scope creep into Opportunity scoring — found
  none, verdict PASS.

### 7.7 Definition of Done

- [x] `ContentIntelligenceSynthesis` model exists with `profile_id`, `summary`,
      `key_themes`, `supporting_analyses`, `generated_at`, `generation_source`,
      `is_current`, `is_stale`.
- [x] Database-level partial unique index enforces exactly one
      `is_current=true` row per profile.
- [x] `strategic_synthesis` AI task registered and run via the Day 15 job
      queue — never synchronously in a request.
- [x] Fewer than two available component analyses, or AI provider failure,
      produce `insufficient_data` / `ai_fallback` rather than a fabricated
      synthesis.
- [x] Any component analysis regenerating marks the synthesis stale without
      eagerly regenerating it.
- [x] GET endpoint returns current synthesis or enqueues regeneration and
      returns a job-status body, consistent with the Day 15/16 pattern.
- [x] Historical synthesis rows are preserved on regeneration.
- [x] Synthesis is cached with a longer TTL than component analyses.
- [x] Workspace/profile ownership enforced with 404 on any chain mismatch.
- [x] Tests cover grounded synthesis, insufficient-data fallback, AI-provider
      fallback, staleness triggers (both Brand and Performance sources),
      regeneration history, cache behavior, and ownership isolation.
- [x] Full regression suite passes (266 tests).
- [x] Ruff check and format check clean for touched files.
- [x] Single migration head (`q0r1s2t3u4`).
