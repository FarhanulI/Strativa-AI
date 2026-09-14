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

## Amendment (2026-09-14) — grounding_basis and stated-data grounding

Patched after initial implementation: the original `insufficient_data`
threshold treated "no accumulated signal/record history yet" the same as
"no data at all," which incorrectly penalized brand-new creator profiles —
immediately after onboarding, a profile already has stated positioning,
stated target audience, and stated topics/expertise, which are valid
grounding data independent of live engagement or published-content
history.

- **Audience Intelligence scope**: `audience_analysis` grounding now also
  accepts onboarding-stated profile data — the profile's stated
  description/goals, and the `AudienceIntelligence` root's stated
  summary/geography/language/demographics/psychographics — as sufficient
  grounding when no persona/pain-point history exists yet. The minimum
  remains "at least one persona and one pain point" **or** at least one
  stated field; it is no longer "signal records only."
- **Market Intelligence scope**: `market_analysis` grounding now also
  accepts the profile's stated topics/expertise/positioning (and the
  `MarketIntelligence` root's stated `summary`, when a root exists) as
  sufficient grounding when no topic/market-signal history exists yet. A
  `MarketIntelligence` root is no longer required to exist at all for
  market analysis to run — the profile's own stated fields are enough on
  their own.
- **`grounding_basis` column**: `AudienceAnalysis` and `MarketAnalysis`
  (not `BrandAnalysis` — its grounding data was already always
  profile-stated) each gained a `grounding_basis` column
  (`stated` | `observed` | `mixed`), set from
  `GroundingResult.grounding_basis` in `app/services/intelligence/grounding.py`.
  `grounded_on` records which stated fields were used via `stated:<field>`
  entries (e.g. `stated:profile.positioning`) alongside any real record
  ids. Migration `s2t3u4v5w6` adds the column and backfills every
  pre-existing `ai`/`ai_fallback` row to `observed` (the stated-data path
  did not exist before this patch); `insufficient_data` rows are left
  `NULL`.
- This does not change behavior for any profile that already has real
  signal data (`observed` sufficiency is checked first and is unaffected)
  — it only expands what counts as sufficient for a profile that doesn't
  have any yet.

### Testing (added by this amendment)

- `test_stated_only_grounding_for_new_profile` (parametrized over
  audience/market, `tests/test_intelligence_analysis.py`): a profile with
  zero persona/pain-point or topic/market-signal history but onboarding
  -stated fields set (description/goals for audience; topics/expertise/
  positioning for market) generates with `generation_source=ai`,
  `grounding_basis=stated`, and `grounded_on` containing at least one
  `stated:`-prefixed entry.
- Full pre-existing Day 16 regression suite (insufficient-data fallback,
  grounded generation, AI-failure fallback, regeneration on material data
  change, ownership isolation) passes unchanged — none of those tests seed
  stated-only profile fields, so their outcomes are untouched.

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
