# Day 18 — Opportunity Reasoning Upgrade

Read and follow:
- `docs/product/product-architecture.md` (Content Opportunity section,
  Deterministic vs LLM Responsibilities, Architectural Rule)
- `docs/development/progress.md` (Days 7, 15, 17)
- `app/ai/strategy/opportunity_scorer.py` — inspect but do NOT modify the
  scoring logic itself this day.
- `docs/development/day-17.md` — the profile's current Content Intelligence
  Synthesis, which this day grounds its reasoning in.

## Objective

Add an `opportunity_reasoning` AI task that generates
`ContentOpportunity.strategic_rationale` from the existing deterministic
score components plus the profile's current Content Intelligence
Synthesis, without changing the score, ranking, or any deterministic
opportunity logic.

## In scope

- `opportunity_reasoning` AI task: input is the opportunity's deterministic
  score components plus the profile's current `ContentIntelligenceSynthesis`;
  output is a natural-language `strategic_rationale`.
- HARD BOUNDARY: score, components, and ranking are completely unchanged
  by this day. If implementing this tempts a scoring-formula change, stop
  — that is out of architectural scope for this day.
- Opportunity is persisted immediately at creation with a deterministic
  placeholder rationale (short templated sentence from score components);
  async reasoning job (Day 15 queue) updates `strategic_rationale` in place
  once complete. The opportunity must be usable instantly, never blocked
  on an LLM call.
- Deterministic fallback: no current synthesis yet for the profile, or AI
  provider failure, leaves the templated placeholder as final, marked
  `generation_source=deterministic`.

## Out of scope

- Any change to scoring, priority mapping, or lifecycle status.
- Learning-alignment scoring factor (a later day in this plan) — that's a
  scoring change, distinct from this rationale-only change.

## System design

Add `rationale_generation_source` and `rationale_generated_at` columns to
`ContentOpportunity` — no change to score-related columns. Bulk opportunity
creation must fan out one async reasoning job per opportunity rather than
looping synchronously. Rate-limit reasoning generation per profile using
the Day 15 rate limiter so a burst of new signals doesn't spike AI cost;
queue excess rather than drop.

## Architecture

Extend the existing opportunity service with a reasoning-enrichment step
that runs AFTER deterministic creation via an async job — mirrors the
existing deterministic-first-then-enriched pattern from Day 11/12, adapted
to async.

## Security

Standard ownership chain, unchanged from Day 7.

## Testing

Opportunity created instantly with placeholder rationale; async reasoning
completes and updates rationale in place; reasoning is grounded in the
correct synthesis content (not hallucinated — assert on content
correspondence); no-synthesis fallback; AI-failure fallback; score/rank
byte-identical before and after this change (regression-critical); bulk
creation produces N independent reasoning jobs, not a blocking loop.

Update `docs/development/progress.md`.

## Definition of Done

Tests + full regression pass, with explicit verification that all existing
Day 7/14 opportunity scoring tests are unchanged in outcome.

## Implementation note

Executed as scoped above. See `docs/development/progress.md`'s "Day 18 -
Opportunity Reasoning Upgrade" entry for the file-by-file summary and
verification results (9 new tests in `tests/test_opportunity_reasoning.py`,
full 275-test regression suite passing, Ruff clean, single migration head
`r1s2t3u4v5`).
