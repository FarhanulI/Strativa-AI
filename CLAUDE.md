# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Backend API for AI Content Studio — an AI-powered Content Operating System, built as a FastAPI modular monolith. It is a content **strategy and intelligence** system (Understand → Decide → Brief → Create → Publish → Measure → Learn), not a raw AI content generator, trend feed, analytics dashboard, or scheduler.

Full product architecture and rules live in [.github/copilot-instructions.md](.github/copilot-instructions.md) and [docs/product/product-architecture.md](docs/product/product-architecture.md) — **read these before making any non-trivial change**; they define product concepts (ContentProfile, ContentOpportunity, ContentBrief, the four Intelligence domains) and hard architectural boundaries (e.g. trends never directly trigger AI generation).

Development proceeds in numbered "days," each scoped by a doc in `docs/development/day-NN.md`. Check the latest day file for current in-progress scope before assuming a feature is missing or extending one — the docs also list what is explicitly out of scope for that day.

## Commands

```bash
uv sync                                    # install dependencies
uv run uvicorn app.main:app --reload --port 8000   # run the API
uv run alembic upgrade head                # apply migrations
uv run alembic revision -m "..."           # create a migration (inspect existing models/migrations first)
uv run pytest                              # run all tests
uv run pytest tests/test_content_briefs.py # run a single test file
uv run pytest tests/test_content_briefs.py::test_name -v  # run a single test
uv run ruff check .                        # lint
uv run ruff format --check .               # format check
```

Tests use an in-memory SQLite database (see [tests/conftest.py](tests/conftest.py)) via `db_session`/`override_get_db` fixtures — no running Postgres/Redis needed to run the suite. `asyncio_mode = "auto"` (pytest-asyncio), so async test functions don't need `@pytest.mark.asyncio`.

## Architecture

### Request flow (strict layering)

```
Router (app/api/v1/*)  →  Service (app/services/*)  →  Repository (app/repositories/*)  →  SQLAlchemy models (app/models/*)
```

- **Router**: HTTP concerns only — request validation, response serialization, DI. Stays thin.
- **Service**: business rules, workspace/profile/parent ownership validation, cross-entity checks, orchestration. This is where authorization lives.
- **Repository**: persistence only (queries, filtering, sorting, CRUD). Never contains authorization logic.

`app/schemas/*` holds Pydantic request/response models — SQLAlchemy models are never exposed directly as API contracts. Server-controlled fields (ids, `*_version`, `generation_source`, `status` transitions, `metadata`) must be stripped/ignored from client input in the service layer, not just omitted from the schema.

### Domain model

`ContentProfile` (type: `creator` | `business` | `personal_brand` | `expert` | `coach` | `startup` | `local_business` | `ecommerce_brand`) is the universal strategic root, owned by exactly one `Workspace`. There is one Content Intelligence/Strategy architecture for all profile types — never fork a "creator" vs "business" version of a model/service/repository. `BusinessContext` (products, services, offers) is an optional extension for commercial profiles and must never become a hard dependency of universal intelligence or strategy code.

Four intelligence domains hang off a profile: Brand, Audience (`Persona`, `PainPoint`, `Desire`, `AudienceQuestion`, `AudienceSignal`), Market (`Topic`, `MarketSignal`, `Competitor`), Performance (`ContentPerformance` → `PerformanceAnalysis` → `PerformanceInsight`).

Strategy pipeline (each stage traceable to the ones before it):

```
Signal (MarketSignal | AudienceSignal | PerformanceInsight)
   → ContentOpportunity (app/ai/strategy/opportunity_scorer.py scores it against profile/audience/goals/performance)
   → ContentBrief (app/services/brief/composer.py — deterministic-first, optional AI enrichment)
   → [future] Content Creation → Publishing → Performance Intelligence → Learning
```

`ContentBrief` is a strategic contract (angle, big idea, tone, CTA strategy, key points) — never final creative copy (no hooks/captions/scripts/assets). Composition is two-stage: Stage A builds a complete brief deterministically from the opportunity + intelligence; Stage B optionally enriches via the AI Router and must never cause Stage A's output to be lost if it fails (`generation_source` falls back to `deterministic`).

Every resource lookup must validate the full ownership chain (`Workspace → ContentProfile → ... → resource`); a mismatch at any level returns **404**, never 403/400, so cross-tenant resource existence is never leaked.

### AI infrastructure (`app/services/ai/`, `app/ai/`)

Provider-agnostic pipeline: `AITask` (what the product wants) → `AIRouter` (`app/services/ai/router.py`, selects provider/model per `TASK_PROVIDER_POLICY` in `policies.py` and `ModelRegistry` capabilities) → `AIProvider` (`StructuredGenerationProvider` protocol in `app/services/ai/base.py`) → concrete provider (`app/services/ai/providers/gemini.py`).

Callers request **structured** output (`AIRequest.response_model`, a Pydantic model) — never raw prose — and get back a validated `Result` plus `AIResponseMetadata` (provider, model, latency). Domain composers (e.g. `BriefComposer`) must go through the router and must never import a provider SDK or call a provider directly; if all providers fail, `AIProviderUnavailableError` is raised and callers fall back to their deterministic path rather than failing the whole request.

`app/workers/` wires `arq` to Redis for background jobs (`WorkerSettings.functions` — currently empty; no jobs registered yet).

### Conventions to match, not reinvent

- UUID primary keys, timezone-aware timestamps, JSONB `metadata` for flexible/lineage data (never duplicate a top-level column's value inside `metadata`).
- Status/enum fields follow existing patterns (e.g. `OpportunityStatus`); version fields are plain top-level string columns (`brief_version = "v1"`), not buried in JSONB.
- New endpoints are versioned and hierarchical: `/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs`, mirroring the ownership chain.
- Before adding anything (model, service, repository, generic abstraction), check whether an equivalent already exists for a sibling domain (Persona/PainPoint/Desire/AudienceQuestion, or MarketSignal/AudienceSignal/PerformanceInsight) and follow that shape rather than inventing a new one.
- Don't add infrastructure (Docker, Kubernetes, message brokers, embeddings/vector DB, multi-agent orchestration) unless a specific development day explicitly calls for it — this is intentionally a single deployable modular monolith at this stage.
