# Backend Architecture Rules

## Scope

These rules apply to backend architecture and domain implementation.

## Architecture

Use a modular monolith.

Preferred dependency direction:

API / Router
↓
Service
↓
Repository
↓
Database

Do not allow repositories to contain business rules.

Do not allow routers to contain substantial business logic.

Services coordinate domain behavior.

## Domain Ownership

ContentProfile is the universal strategic root.

BusinessContext is optional.

Never create separate Creator and Business strategy domains.

Use shared domain models whenever the business concept is universal.

## Relationships

Before adding a relationship:

1. identify the aggregate/root entity
2. identify ownership
3. determine cardinality
4. determine delete behavior
5. determine indexing requirements
6. add tests for ownership boundaries

## Workspace Security

Every workspace-owned resource must be traceable to its Workspace.

Never rely solely on an ID provided by the client.

Validate parent-child ownership in the service layer.

Cross-workspace access should return 404.

## Database

Use SQLAlchemy ORM.

Use Alembic for schema changes.

Prefer explicit foreign keys.

Use cascade behavior deliberately.

Do not use database relationships as a substitute for authorization.

## Product Boundaries

Keep these concepts separate:

MarketSignal
ContentOpportunity
ContentBrief
ContentItem
PerformanceInsight

A MarketSignal is intelligence.

A ContentOpportunity is a strategic decision.

A ContentBrief is a creation contract.

A ContentItem is an actual content unit.

A PerformanceInsight explains observed performance.

Never collapse these concepts into one model.

## Extensibility

Build for future AI and external integrations without implementing them prematurely.

External data should eventually enter through ingestion/integration boundaries.

AI should eventually operate through service boundaries.

Do not couple domain models directly to a specific AI provider.
