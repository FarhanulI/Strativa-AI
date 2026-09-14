# Day 16 — Intelligence Reasoning Layer: Brand, Audience & Market Analysis

Read and follow:
- `docs/product/product-architecture.md` (Content Intelligence, Brand/
  Audience/Market Intelligence sections, Deterministic vs LLM
  Responsibilities, Architectural Rule: "The LLM is the reasoning layer,
  not the source of truth")
- `docs/development/progress.md` (Days 3, 4, 5, 9, 10, 15)

Inspect the existing Performance Intelligence AI-reasoning implementation
from Day 9 first — it already does what this day does for one domain. Reuse
its pattern rather than inventing a new one.

## Objective

Add an LLM reasoning layer over Brand, Audience, and Market Intelligence,
grounded in each domain's stored data, run as an async job via the Day 15
job infrastructure, with a deterministic fallback.

## In scope

- Three AI tasks: `brand_analysis`, `audience_analysis`, `market_analysis`,
  registered in the existing task policy alongside `performance_analysis`.
- Stored analysis result per domain per profile: `BrandAnalysis(profile_id,
  insights, grounded_on [array of source record ids], generated_at,
  generation_source [ai | ai_fallback | insufficient_data])`, and the
  equivalent `AudienceAnalysis`, `MarketAnalysis` models.
- Generation triggered on demand via an async job (Day 15 queue) or when
  underlying domain data changes materially (any create/update/delete on
  that domain's core records). Do not regenerate on trivial reads.
- Deterministic fallback: if the AI provider fails, or the domain lacks a
  defined minimum of underlying data (e.g. Audience requires at least one
  persona and one pain point — define minimums per domain), store a result
  with `generation_source=insufficient_data` or `ai_fallback` and a plain
  templated message. Never fabricate an insight not grounded in stored
  data.
- GET endpoint per domain returning the latest current analysis, enqueuing
  generation if missing/stale and returning a pending-job status
  (consistent with Day 15's job status pattern) rather than blocking.

## Out of scope

- Combining the three analyses into one strategic picture — Day 17
  (renumbered; see note below).
- Any change to Performance Intelligence, which already has this pattern.
- Any change to Opportunity Engine scoring.

## Architecture

Prefer a single shared `intelligence_analysis` module parameterized by
domain over triplicating near-identical code across Brand/Audience/Market,
as long as each domain's grounding-data access remains domain-scoped and
ownership-checked independently.

## System design

Index each analysis table on `(profile_id, generated_at DESC)` or maintain
an `is_current` flag for O(1) latest-analysis lookup. Generation always
goes through the Day 15 `ai_jobs` queue — the API endpoint enqueues and
returns; it never blocks the request on the AI call. Cache the
latest-analysis read via Day 15's `CacheService`, invalidated explicitly on
regeneration rather than relying on TTL alone.

## Security

Standard workspace/profile ownership chain; a caller unable to read a
profile's underlying domain data cannot trigger or read its analysis
either (404, never 403/400).

## Testing

Grounded generation against seeded data (assert `grounded_on` references
real ids), insufficient-data fallback per domain, AI-provider-failure
fallback, regeneration on material data change, cache invalidation on
regeneration, ownership isolation (404).

## Definition of Done

Tests + regression pass, all three domains verified against a shared
parameterized test harness, ruff clean, migration reversible.

## Numbering note

This work was scoped by its author as "Day 16." At the time it was
executed, `docs/development/progress.md` already had a completed and
documented Day 16 (Content Library) and Day 17 (Publishing Foundation).
Per explicit instruction from the project owner, this feature keeps the
Day 16 slot as-is; the prior Day 16 (Content Library) entry in
`progress.md` is left untouched and will be reconciled/renumbered later by
the project owner. `progress.md` therefore temporarily contains two
"Day 16" sections — this one (Intelligence Reasoning Layer) and the
pre-existing one (Content Library) — until that reconciliation happens.
