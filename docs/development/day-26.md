# Day 26 - Learning Engine v1 + Intelligence Feedback Loop Closure

## Objective

Extract durable strategic patterns from `PerformanceAnalysis`/`PerformanceInsight`
into a new `Learning` entity, and wire active learnings into the deterministic
`opportunity_scorer` as a bounded, capped scoring factor — closing the
Learning Loop described in `docs/product/product-architecture.md`
("Performance and Learning," "Learning Loop," Principle 12: "Learning Must
Feed Strategy").

Full architectural context: `docs/product/product-architecture.md` and
`docs/development/progress.md` (Day 7 opportunity scoring, Day 15 job/cron
infrastructure, Day 21 ownership-chain enforcement).

## Scope

In scope — Learning Engine:

- `Learning` model: `profile_id`, `pattern_description`,
  `supporting_evidence` (`PerformanceInsight`/`PerformanceAnalysis` ids),
  `confidence_level`, `dimension`
  (`format | topic | pillar | hook_style | cta | timing`), `status`
  (`active | superseded`).
- Deterministic pattern extraction as a Day 15 scheduled periodic job (not
  triggered per-metrics-submission): when at least N `PerformanceAnalysis`
  records exist for a profile, compare performance across dimension values
  and surface statistical deltas as candidate learnings. Runs on a
  configurable cadence per active profile (nightly).
- `learning_explanation` AI task enriches the explanation text only, with a
  deterministic templated fallback on AI failure.
- CRUD/list API for learnings per profile.

In scope — Feedback Loop Closure:

- Extend `opportunity_scorer` with a `learning_alignment` factor: matches a
  new opportunity's pillar/format/topic against active `Learning`
  dimension+value, applies a small, explicitly-capped score adjustment.
  Weight documented in code and here.
- `strategic_rationale` (already LLM-reasoned per Day 18) references the
  influencing learning when one applies.

Explicitly out of scope this day:

- Automatic learning supersession beyond a simple status flag.
- Any change to Brief/Draft/Variation/Evaluation scoring.

Architecture constraints:

- New `app/learning/` domain module, a read-only consumer of Performance
  repositories — extraction logic never lives in the Performance module.
- `opportunity_scorer.py` is extended as a targeted addition, not a parallel
  scoring path.
- `Learning` is indexed on `(profile_id, status, dimension)` for the
  scorer's per-opportunity lookup — a cheap indexed read, not a scan, since
  it runs on every opportunity creation.
- Extraction runs as a batch job, not synchronously per metric submission,
  to control cost at scale, and must be idempotent — running it twice for
  the same period must not duplicate learnings.

Security: standard ownership chain (workspace → profile → learning) for
Learning CRUD/list, via `require_profile_access`, matching Day 21 — a
mismatch at any level is a 404, never 403/400.

## Implementation

### `Learning` model (`app/models/learning.py`)

- `dimension` (`LearningDimension` enum: format/topic/pillar/hook_style/
  cta/timing), `dimension_value`, `pattern_description`,
  `confidence_level` (`CheckConstraint` 0–1) — always deterministic,
  extraction-job-owned, never client-writable.
- `explanation` + `explanation_generation_source`
  (`ExplanationGenerationSource`: `ai | deterministic`) — mirrors the
  `ContentOpportunity` rationale-provenance pattern; `pattern_description`
  and `confidence_level` are never AI-derived, only the natural-language
  `explanation` text may be.
- `supporting_evidence` (JSONB: `PerformanceAnalysis` ids and sample
  stats), `status` (`LearningStatus`: `active | superseded`),
  `extraction_version`.
- `UniqueConstraint(profile_id, dimension, dimension_value)` — makes the
  nightly extraction job's upsert idempotent.
- `Index(profile_id, status, dimension)` — the scorer's per-opportunity
  lookup runs against this composite index, not a scan.
- Migration `c8d9e0f1a2b3` (new single head).

### Extraction (`app/learning/extraction.py`)

- `extract_learnings_for_profile(session, profile_id, router)`: a
  **read-only consumer** of `ContentPerformanceRepository` — never writes
  to `ContentPerformance`/`PerformanceAnalysis`. Compares each profile's
  per-`format`/per-`topic` average `relative_engagement` (the Day 9/25
  baseline-comparison output) against the profile's overall average. Only
  `format` and `topic` are extracted in v1, since those are the only
  `LearningDimension` values with real structured backing data on
  `ContentPerformance` today; `pillar`/`hook_style`/`cta`/`timing` remain
  valid for manually-created or future learnings.
- A candidate is surfaced only once a profile has at least
  `learning_extraction_min_analyses` (default 6) analyzed records overall,
  a dimension value has at least `learning_extraction_min_group_size`
  (default 3) records, and its relative delta clears
  `learning_extraction_min_delta_threshold` (default 20%) — all three
  configurable per deployment in `app/core/config.py`.
- Upserts via `LearningRepository.get_by_pattern` +
  `(profile_id, dimension, dimension_value)`, so re-running the job for the
  same period updates the existing row instead of duplicating it.
- Calls `LearningExplainer.explain()` (the `learning_explanation` AI task)
  for the natural-language `explanation`; on `AIError`, falls back to the
  deterministic `pattern_description` and records
  `explanation_generation_source = deterministic`, per Principle 16
  (Deterministic First, AI Enriched).
- `extract_learnings_cron(ctx)`: the arq **cron** entrypoint (Day 15
  pattern), running nightly (`learning_extraction_hour`/
  `learning_extraction_minute`, default 3:00 AM) across every profile with
  `ContentPerformance` history, guarded by `try_lock` against redundant
  concurrent runs across worker instances — correctness itself comes from
  the model's unique constraint, so the lock is a performance optimization,
  not the idempotency guarantee.

### CRUD/list API (`app/api/v1/learnings.py`, `app/learning/service.py`)

```text
POST   /api/v1/profiles/{profile_id}/learnings
GET    /api/v1/profiles/{profile_id}/learnings
GET    /api/v1/profiles/{profile_id}/learnings/{learning_id}
PATCH  /api/v1/profiles/{profile_id}/learnings/{learning_id}
DELETE /api/v1/profiles/{profile_id}/learnings/{learning_id}
```

- Standard `require_profile_access` ownership-chain enforcement (404 on any
  mismatch), matching Day 21.
- `LearningUpdate` only accepts `status` — pattern data, confidence, and
  evidence stay extraction-job-owned and are never client-writable,
  matching this repo's schema-layer stripping rule for server-controlled
  fields.

### Feedback loop closure (`app/ai/strategy/opportunity_scorer.py`)

- `OpportunityScorer.score()` extended with a `learning_alignment` factor,
  computed by `calculate_learning_alignment` / `find_matching_learning` —
  matches a new opportunity's recommended format or signal topic against
  active (`LearningStatus.ACTIVE`) learnings on the `format`/`topic`
  dimensions, taking the highest-confidence match.
- Adjustment: `confidence_level * LEARNING_ALIGNMENT_WEIGHT`
  (`LEARNING_ALIGNMENT_WEIGHT = 0.05`), applied **additively on top of** —
  never rebalanced into — the four existing weighted factors
  (`signal_strength` 0.30, `profile_relevance` 0.30, `goal_alignment` 0.20,
  `timeliness` 0.20). It can nudge a score by at most 0.05 and never
  dominates it.
- Defaults to `0.0` whenever no learnings are supplied or none match —
  byte-identical to pre-Day-26 scoring behavior for every profile with zero
  active learnings.
- `ContentOpportunityService.create()` (`app/services/content_opportunity.py`)
  queries `LearningRepository.list_active_for_dimensions` (the indexed
  read on `(profile_id, status, dimension)`) and passes the result into
  `scorer.score()`. The matched `Learning`'s id is recorded on
  `opportunity_metadata.influencing_learning_id` alongside the existing
  `score_components`.
- `strategic_rationale` (`app/services/opportunity_reasoning.py`,
  `generate_rationale`) looks up `influencing_learning_id` from that
  metadata when present, re-validates it against the opportunity's own
  `profile_id`, and passes the learning's `dimension`/`dimension_value`/
  `pattern_description`/`explanation` into the `opportunity_reasoning` AI
  task's context as `influencing_learning`, so the LLM-reasoned rationale
  can explicitly cite the pattern as evidence.

## Migration

- `c8d9e0f1a2b3` (new single head): creates the `learnings` table with the
  `dimension`/`status` enums, the confidence `CheckConstraint`, the
  `(profile_id, dimension, dimension_value)` unique constraint, and the
  `(profile_id, status, dimension)` composite index.

## Testing

`tests/test_learning.py` — 10 tests, all passing:

- scorer baseline regression: `learning_alignment` defaults to `0.0` and
  `total` is unchanged when no active learnings are supplied;
- a capped-bonus case on a format match;
- superseded learnings ignored by the matcher;
- extraction surfacing a clearly-separated high-performing format against
  synthetic data, and re-running idempotently (no duplicate rows);
- a below-minimum-analyses profile correctly skipped (threshold-not-met
  case);
- AI-enriched vs. deterministic-fallback explanation generation;
- full CRUD/list;
- cross-tenant 404 ownership isolation;
- an end-to-end integration test confirming an active learning both raises
  a new opportunity's score/metadata and reaches the
  `opportunity_reasoning` AI context verbatim.

Verification (all actually executed):

- `uv run pytest tests/test_learning.py -v` → **10 passed**.
- `uv run ruff check` / `uv run ruff format --check` over Day 26 files
  (model, repository, schema, extraction, service, router, migration, test
  file): clean.

## Known limitations

- Only `format` and `topic` are extractable in v1; `pillar`, `hook_style`,
  `cta`, and `timing` have no structured backing data on
  `ContentPerformance` today and require manual creation via the CRUD API
  until a future day adds that data.
- Automatic learning supersession is out of scope — an operator or future
  process must set `status = superseded` explicitly; nothing currently
  retires a stale learning on its own.
- `learning_alignment` only compares against a new opportunity's
  recommended format or signal topic; it does not yet consider content
  pillar matching even though `LearningDimension.PILLAR` exists as a valid
  value for manually-created learnings.

## Files changed

- New: `app/models/learning.py`, `app/repositories/learning.py`,
  `app/schemas/learning.py`, `app/learning/__init__.py`,
  `app/learning/extraction.py`, `app/learning/service.py`,
  `app/services/llm/learning_explainer.py`, `app/api/v1/learnings.py`,
  `migrations/versions/c8d9e0f1a2b3_add_learnings.py`,
  `tests/test_learning.py`.
- Modified: `app/ai/strategy/opportunity_scorer.py`
  (`learning_alignment`/`LEARNING_ALIGNMENT_WEIGHT`/
  `calculate_learning_alignment`/`find_matching_learning`),
  `app/services/content_opportunity.py` (queries active learnings and
  records `influencing_learning_id`), `app/services/opportunity_reasoning.py`
  (passes `influencing_learning` into the AI context), `app/core/config.py`
  (`learning_extraction_min_analyses`/`min_group_size`/
  `min_delta_threshold`/`hour`/`minute`), `app/workers/settings.py`
  (registers `extract_learnings_cron`), `docs/development/progress.md`
  (Day 26 entry).
