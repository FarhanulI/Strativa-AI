# AI Content Studio — Backend Copilot Instructions

## 1. Project

This repository is the backend of AI Content Studio.

AI Content Studio is an AI-powered Content Operating System that helps businesses and creators:

Understand → Decide → Brief → Create → Publish → Measure → Learn

The product's core value is intelligent, personalized content strategy.

It is NOT primarily:

* an AI content generator
* a trend feed
* an analytics dashboard
* a social media scheduler
* an AI image generator
* an AI video generator

Those are execution components around the central strategy system.

---

## 2. Universal Product Architecture

The universal strategic root entity is:

ContentProfile

Supported profile types include:

* creator
* business
* personal_brand
* expert
* coach
* startup
* local_business
* ecommerce_brand

Do NOT create separate strategy engines for different profile types.

Creators and businesses must use the same Content Intelligence and Content Strategy architecture.

Business-specific information belongs in an optional:

BusinessContext

Creators must be fully supported without BusinessContext.

---

## 3. Core Product Loop

The permanent product loop is:

Understand
→ Decide
→ Brief
→ Create
→ Publish
→ Measure
→ Learn
→ Understand

The strategic architecture is:

Content Intelligence
→ Content Strategy
→ Content Opportunity
→ Content Brief
→ Content Creation
→ Publishing
→ Performance Intelligence
→ Learning
→ Content Intelligence

---

## 4. Content Intelligence

Content Intelligence is the central brain.

It contains four major intelligence domains:

### Brand Intelligence

Understands:

* identity
* positioning
* voice
* tone
* visual identity
* USP
* topics
* expertise
* content pillars
* goals
* existing content

### Audience Intelligence

Understands:

* audience
* personas
* pain points
* desires
* questions
* objections
* motivations
* language
* content preferences
* engagement behavior

### Market Intelligence

Understands:

* topics
* trends
* market signals
* competitors
* creator benchmarks
* market conversations
* emerging opportunities

### Performance Intelligence

Understands:

* what content worked
* what failed
* why it worked
* why it failed
* winning hooks
* format patterns
* audience behavior
* retention
* engagement
* CTA effectiveness
* creative patterns

---

## 5. Critical Strategy Rule

NEVER implement:

Trend
→ Generate Content

The required architecture is:

Trend / Signal
+
Profile
+
Audience
+
Performance
+
Goals
→ Opportunity
→ Brief
→ Creation

Market intelligence is an input to strategy.

It is not an automatic content generator.

---

## 6. Content Opportunity

A ContentOpportunity represents a strategically evaluated reason for a profile to create content.

It is NOT:

* a raw trend
* a raw topic
* a caption
* a content asset
* a ContentBrief

The conceptual relationship is:

ContentProfile
→ ContentOpportunity
→ ContentBrief
→ ContentItem

An opportunity may originate from:

* trend
* performance_gap
* audience_question
* pillar_rotation
* market_conversation

Do not make trends the only source.

---

## 7. Creator Support

Creators are first-class users of the platform.

A creator may have:

ContentProfile
+
Brand Intelligence
+
Audience Intelligence
+
Market Intelligence
+
Performance Intelligence

without:

BusinessContext

Do not make products, services, offers, or sales objectives mandatory for creators.

Examples of creator goals:

* growth
* authority
* engagement

Creators may create content about any topic, including:

* sports
* football
* photography
* fitness
* comedy
* education
* lifestyle
* gaming
* travel
* technology

Do not hard-code the system around business marketing.

---

## 8. Business Support

Businesses may optionally have:

BusinessContext

containing:

* products
* services
* offers
* commercial objectives

BusinessContext must remain modular.

Do not move universal intelligence concepts into BusinessContext.

---

## 9. Backend Technology

Use:

* Python
* FastAPI
* SQLAlchemy ORM
* PostgreSQL
* Alembic
* Pydantic
* uv
* pytest
* Ruff

The MVP is a modular monolith.

---

## 10. Repository Architecture

Prefer:

HTTP
→ Router
→ Service
→ Repository
→ SQLAlchemy
→ PostgreSQL

### Router

Responsible for:

* HTTP concerns
* request validation
* response serialization
* dependency injection

Routers should remain thin.

### Service

Responsible for:

* business rules
* authorization
* ownership validation
* orchestration
* domain decisions

### Repository

Responsible for:

* database persistence
* SQLAlchemy queries
* retrieval
* filtering
* updates
* deletes

Repositories must not contain business authorization rules.

---

## 11. Database Principles

Use PostgreSQL as the primary database.

Use UUIDs for domain entity identifiers where that convention is already established.

Use timezone-aware timestamps.

Use foreign keys with intentional delete behavior.

Use indexes where queries require them.

Use JSONB only where flexible metadata is genuinely useful.

Do not add database fields merely for speculative future functionality.

---

## 12. Workspace Isolation

All data is workspace-scoped.

Conceptually:

Workspace
→ ContentProfile
→ Intelligence
→ Strategy
→ Content
→ Performance

Every resource lookup must verify ownership through the appropriate parent relationship.

Cross-workspace resource access should return 404 rather than exposing resource existence.

Never trust workspace or parent IDs supplied by clients without validation.

---

## 13. Migrations

All database schema changes require Alembic migrations.

Never manually modify production schema.

Before creating a migration:

1. inspect existing models
2. inspect existing migrations
3. understand relationships
4. create the smallest necessary migration

Do not rewrite unrelated migrations.

---

## 14. API Design

Use versioned APIs.

Preferred structure:

`/api/v1/...`

Use RESTful resource naming.

Prefer hierarchical routes when ownership relationships matter.

Example:

`/api/v1/profiles/{profile_id}/opportunities`

Keep request and response schemas separate where appropriate.

Never expose SQLAlchemy models directly as API contracts.

---

## 15. Validation

Validate at multiple levels:

* Pydantic request validation
* service/domain validation
* database constraints

Never rely exclusively on frontend validation.

Important domain rules must be enforced server-side.

---

## 16. AI Integration

Do not introduce LLM integrations unless the current development day explicitly requires them.

Do not add OpenAI, Anthropic, Gemini, embeddings, vector databases, or agent frameworks simply because they may be useful later.

First establish deterministic domain infrastructure.

When AI is eventually introduced, keep it behind modular service boundaries.

---

## 17. Do Not Over-Engineer

This is an MVP.

Prefer:

simple
clear
testable
modular
maintainable

over:

complex
distributed
prematurely scalable

Do not introduce abstractions without a concrete use case.

Do not create generic repositories, generic services, event buses, or plugin systems unless explicitly required.

---

## 18. Existing Code Comes First

Before modifying the codebase:

1. inspect the existing implementation
2. understand existing naming conventions
3. inspect related models
4. inspect relationships
5. inspect existing services
6. inspect repositories
7. inspect API patterns
8. inspect tests
9. inspect migrations

Follow established project conventions when they are sound.

Do not rewrite working code merely because another pattern is personally preferred.

---

## 19. Daily Development Protocol

When implementing a development day:

1. Read the permanent project instructions.
2. Read the requested `docs/development/day-XX.md`.
3. Inspect all relevant existing code.
4. Identify dependencies on previous development days.
5. Make a short implementation plan.
6. Implement only the requested scope.
7. Add or update database migrations.
8. Add tests.
9. Run tests.
10. Run Ruff.
11. Run formatting checks.
12. Fix failures.
13. Review for architectural consistency.
14. Report exactly what changed.
15. Stop.

Do not implement future development days.

---

## 20. Definition of Done

A development day is complete only when:

* implementation exists
* database migrations exist when required
* tests exist
* tests pass
* lint passes
* formatting passes
* relationships are correct
* workspace isolation is preserved
* existing functionality is not unnecessarily broken
* the implementation follows the product architecture

---

## 21. Comments

Use comments to explain:

* architectural intent
* non-obvious business rules
* unusual database behavior
* important security decisions

Do not add comments that simply restate the code.

Bad:

`# Create opportunity`

Good:

`# Market signals are intelligence inputs and must be evaluated against profile context before becoming opportunities.`

---

## 22. Future Architecture

The backend is being built toward:

ContentProfile
│
├── Brand Intelligence
├── Audience Intelligence
├── Market Intelligence
│   ├── Topics
│   ├── Signals
│   └── Competitors
├── Performance Intelligence
│
├── Content Strategy
├── Content Opportunity
├── Content Brief
├── Content Item
├── Asset
├── Publishing
└── Learning

Do not implement all of these at once.

Implement the current development day only.

---

## 23. Final Rule

Every backend feature should strengthen the core loop:

Understand
→ Decide
→ Brief
→ Create
→ Publish
→ Measure
→ Learn

Avoid disconnected features that do not contribute to this loop.
