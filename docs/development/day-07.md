# Day 7 — Content Opportunity Engine

## Status

Planned

## Objective

Implement the first version of the **Content Opportunity Engine**.

The engine converts structured intelligence signals into strategically evaluated content opportunities.

The core flow becomes:

```text
Content Intelligence
        ↓
Market / Audience / Performance Signal
        ↓
Opportunity Evaluation
        ↓
ContentOpportunity
```

The system must NOT directly generate content from a trend.

The required strategic flow is:

```text
Signal
+
ContentProfile
+
Audience Context
+
Goals
+
Performance Context
        ↓
Content Opportunity
        ↓
Content Brief (future day)
```

Day 7 stops at `ContentOpportunity`.

---

# 1. Product Purpose

A `ContentOpportunity` represents a reason why a specific ContentProfile should consider creating a piece of content.

It is a strategic decision, not simply a trend.

Examples:

### Business

```text
Signal:
"Short-form product comparison videos are receiving unusually high engagement."

Profile:
Affordable premium sportswear brand

Opportunity:

"Create a short-form comparison showing budget vs premium
training shoes for young athletes."

Objective:
Growth
```

### Creator

```text
Signal:
"Football tactical breakdowns are receiving high engagement."

Profile:
Football creator

Opportunity:

"Create a simple tactical breakdown explaining why a team
creates overloads on the left side."

Objective:
Authority
```

### Comedy Creator

```text
Signal:
A particular meme format is accelerating.

Profile:
Comedy creator

Opportunity:

"Adapt the format into a relatable football-fan situation."

Objective:
Growth
```

The Opportunity Engine must support all these cases through the same architecture.

---

# 2. Universal Profile Support

The engine must work with:

* creator
* business
* personal_brand
* expert
* coach
* startup
* local_business
* ecommerce_brand

Do NOT create separate opportunity models.

Use:

```text
ContentProfile
        ↓
ContentOpportunity
```

Do NOT create:

```text
CreatorOpportunity
BusinessOpportunity
```

---

# 3. BusinessContext

`BusinessContext` is optional.

A creator must be able to use the Opportunity Engine without:

* products
* services
* offers
* commercial objectives

The Opportunity Engine must therefore rely primarily on universal ContentProfile information.

Business-specific context may improve an opportunity when available, but it must not be required.

---

# 4. ContentOpportunity Domain Model

Create a `ContentOpportunity` model.

Conceptually:

```text
ContentProfile
      │
      │ 1:N
      ▼
ContentOpportunity
      │
      │ optional
      ▼
MarketSignal
```

Recommended fields:

```text
id
profile_id
market_signal_id
source_signal
title
strategic_rationale
target_objective
recommended_format
relevance_score
opportunity_score
priority
status
expires_at
metadata
created_at
updated_at
```

Use the project's established:

* UUID conventions
* timestamp conventions
* enum conventions
* SQLAlchemy patterns

Do not introduce a new convention if the repository already has one.

---

# 5. Source Signal

`source_signal` identifies why the opportunity exists.

Supported values:

```text
trend
performance_gap
audience_question
pillar_rotation
market_conversation
```

This should be represented using the project's established enum pattern.

Do not make `trend` the only source.

---

# 6. Target Objective

The initial supported objectives are:

```text
growth
authority
lead_gen
sales
```

These should use the existing project conventions for strategy goals/objectives.

Creators may primarily use:

```text
growth
authority
```

Businesses may use:

```text
growth
authority
lead_gen
sales
```

However, do not hard-code profile types to objectives.

A profile's configured goals should influence scoring.

---

# 7. Status

Initial opportunity statuses:

```text
draft
active
accepted
rejected
expired
```

Use the project's existing enum conventions.

The initial default should be:

```text
draft
```

unless the existing product architecture specifies another default.

---

# 8. Priority

Priority is derived from the calculated opportunity score.

Use:

```text
opportunity_score >= 0.80
    → high

opportunity_score >= 0.50
    → medium

opportunity_score < 0.50
    → low
```

Priority should be calculated by the backend.

Clients must NOT directly submit the calculated priority.

---

# 9. Opportunity Score

Implement deterministic v1 scoring.

The score is:

```text
opportunity_score =
    signal_strength * 0.30
    +
    profile_relevance * 0.30
    +
    goal_alignment * 0.20
    +
    timeliness * 0.20
```

All components must be normalized between:

```text
0.0
```

and

```text
1.0
```

The final score must also be between:

```text
0.0
```

and

```text
1.0
```

Store the scoring version as:

```text
v1
```

Store the score components in `metadata` or the project's appropriate structured field.

Example:

```json
{
  "scoring_version": "v1",
  "score_components": {
    "signal_strength": 0.8,
    "profile_relevance": 0.9,
    "goal_alignment": 1.0,
    "timeliness": 0.7
  }
}
```

---

# 10. Signal Strength

When a `MarketSignal` exists:

```text
signal_strength =
    velocity_score * 0.5
    +
    engagement_score * 0.5
```

Both values must be normalized to `[0, 1]`.

If no MarketSignal exists, use:

```text
signal_strength = 0.5
```

Do not introduce external trend APIs or scraping in Day 7.

---

# 11. Profile Relevance

When a MarketSignal provides a relevance score, use that score.

Otherwise:

```text
profile_relevance = 0.5
```

The relevance value must remain normalized:

```text
0.0 <= profile_relevance <= 1.0
```

Do not build an ML relevance model in Day 7.

Do not use an LLM.

---

# 12. Goal Alignment

Determine whether the opportunity's target objective aligns with the ContentProfile's configured goals.

Initial deterministic rule:

```text
If target objective matches a configured profile goal:
    goal_alignment = 1.0

If goals exist but target objective does not match:
    goal_alignment = 0.5

If the profile has no configured goals:
    goal_alignment = 0.5
```

Keep this logic isolated so it can become more sophisticated later.

---

# 13. Timeliness

Timeliness should represent how relevant the signal is based on time.

When a MarketSignal provides expiration information, calculate timeliness using the remaining useful lifetime of the signal.

Use a simple deterministic v1 approach.

Suggested behavior:

```text
No expiration information:
    timeliness = 0.5

Expired:
    timeliness = 0.0

Active and far from expiration:
    timeliness approaches 1.0

Close to expiration:
    timeliness decreases
```

Keep the calculation isolated inside the scoring component.

Do not build a complex forecasting model.

---

# 14. Scoring Component

Do not put scoring directly inside the API route.

Create a dedicated scoring component/service.

Conceptually:

```text
OpportunityScorer
        │
        ├── calculate_signal_strength()
        ├── calculate_profile_relevance()
        ├── calculate_goal_alignment()
        ├── calculate_timeliness()
        └── calculate_opportunity_score()
```

The scorer should be deterministic and independently testable.

Future versions may replace v1 with:

* ML scoring
* LLM-assisted reasoning
* learned performance signals

Do not implement those now.

---

# 15. Strategic Rationale

Generate a deterministic rationale for the opportunity.

The rationale should explain:

1. What is happening?
2. Why is it relevant to this profile?
3. Why should the profile consider acting on it?
4. Which objective does it support?

Example:

```text
This market signal is gaining engagement and has strong relevance
to the profile's sports audience. Adapting the format to the
profile's expertise can support the growth objective.
```

The rationale must be generated from structured information.

Do NOT use an LLM.

Do NOT hard-code a specific industry.

---

# 16. Recommended Format

The Opportunity Engine may store a recommended content format.

Examples:

```text
reel
short_video
carousel
image
text_post
story
ugc
blitz
remix
```

This is a recommendation, not generated content.

Day 7 does not implement asset generation.

---

# 17. MarketSignal Relationship

A ContentOpportunity may optionally reference a MarketSignal.

Rules:

```text
MarketSignal belongs to ContentProfile
ContentOpportunity belongs to ContentProfile
```

If `market_signal_id` is supplied:

```text
MarketSignal.profile_id
must equal
ContentOpportunity.profile_id
```

If this condition is not satisfied, reject the request.

Never allow:

```text
Profile A
    ↓
Opportunity
    ↓
MarketSignal belonging to Profile B
```

---

# 18. Delete Behavior

When a ContentProfile is deleted:

```text
ContentProfile
    ↓
ContentOpportunity
```

Opportunities should be deleted with the profile.

Therefore use appropriate cascade behavior.

When a MarketSignal is deleted:

```text
MarketSignal
    ↓
ContentOpportunity
```

The opportunity should remain.

Therefore:

```text
market_signal_id → SET NULL
```

unless existing project conventions require an equivalent implementation.

---

# 19. Database Constraints

Add appropriate database constraints.

At minimum:

```text
0.0 <= relevance_score <= 1.0
0.0 <= opportunity_score <= 1.0
```

Add indexes for fields used by the API:

* profile_id
* status
* source_signal
* target_objective
* priority
* opportunity_score

Use composite indexes only when justified by actual query patterns.

Do not add speculative indexes.

---

# 20. Pydantic Schemas

Create appropriate schemas.

At minimum:

```text
ContentOpportunityCreate
ContentOpportunityUpdate
ContentOpportunityResponse
```

Clients may provide:

```text
source_signal
market_signal_id
title
target_objective
recommended_format
```

Clients must NOT directly provide:

```text
opportunity_score
priority
scoring_version
score_components
```

Those are server-calculated.

The server must determine:

```text
profile_id
workspace ownership
opportunity_score
priority
scoring metadata
timestamps
```

---

# 21. API Endpoints

Implement:

```http
POST /api/v1/profiles/{profile_id}/opportunities
```

Create an opportunity.

---

```http
GET /api/v1/profiles/{profile_id}/opportunities
```

List opportunities.

Support filtering by:

```text
status
source_signal
target_objective
priority
```

Support sorting by:

```text
opportunity_score
```

Follow existing pagination conventions if already implemented.

---

```http
GET /api/v1/profiles/{profile_id}/opportunities/{opportunity_id}
```

Retrieve one opportunity.

---

```http
PATCH /api/v1/profiles/{profile_id}/opportunities/{opportunity_id}
```

Update mutable opportunity fields.

Do not allow clients to overwrite server-calculated scores.

---

```http
DELETE /api/v1/profiles/{profile_id}/opportunities/{opportunity_id}
```

Delete an opportunity.

---

# 22. Workspace Isolation

All opportunity operations must respect workspace ownership.

The authorization chain is:

```text
Workspace
    ↓
ContentProfile
    ↓
ContentOpportunity
```

For every operation verify:

```text
current_workspace
    owns
ContentProfile
    owns
ContentOpportunity
```

Cross-workspace access must return:

```text
404 Not Found
```

Do not reveal whether another workspace owns the resource.

---

# 23. Cross-Profile Validation

When creating an opportunity with a MarketSignal:

```text
Opportunity.profile_id
must equal
MarketSignal.profile_id
```

If not:

```text
404 Not Found
```

Do not expose cross-profile resource existence.

---

# 24. Repository

Create a dedicated repository for ContentOpportunity.

It should handle persistence operations such as:

```text
create
get_by_id
list
update
delete
```

Filtering should remain in the repository/database layer.

Do not put domain scoring logic inside the repository.

---

# 25. Service

Create a ContentOpportunity service responsible for:

* validating profile ownership
* validating MarketSignal ownership
* creating opportunities
* invoking OpportunityScorer
* calculating priority
* generating strategic rationale
* updating opportunities
* enforcing domain rules

Conceptually:

```text
API Router
    ↓
ContentOpportunityService
    ↓
OpportunityScorer
    ↓
ContentOpportunityRepository
    ↓
SQLAlchemy
```

---

# 26. Tests

Implement tests for:

### CRUD

* create
* retrieve
* list
* update
* delete

### Scoring

* all components = 1.0
* all components = 0.0
* mixed component values
* score stays within `[0, 1]`

### Priority

```text
0.80 → high
0.50 → medium
0.49 → low
```

### Goal Alignment

Test:

* matching goal
* non-matching goal
* no configured goals

### MarketSignal

Test:

* valid MarketSignal
* no MarketSignal
* MarketSignal from another profile
* MarketSignal from another workspace

### Creator

Test a creator with:

```text
BusinessContext = null
```

and verify that an opportunity can still be created.

### Business

Test a business with BusinessContext.

### Workspace Isolation

Verify Workspace A cannot:

* retrieve Workspace B opportunity
* update Workspace B opportunity
* delete Workspace B opportunity
* reference Workspace B MarketSignal

All should behave as:

```text
404
```

### Filtering

Test:

* status
* source_signal
* target_objective
* priority

### Sorting

Test opportunity-score ascending/descending according to the existing API convention.

---

# 27. Migration

Create an Alembic migration for all required database changes.

Before creating the migration:

1. inspect existing models
2. inspect existing migrations
3. verify foreign keys
4. verify indexes
5. verify constraints
6. verify cascade behavior

Do not modify unrelated migrations.

---

# 28. No AI Integration

Day 7 is deterministic.

Do NOT implement:

* OpenAI
* Anthropic
* Gemini
* LLM calls
* embeddings
* vector search
* AI agents

The architecture must allow these capabilities later without requiring them now.

---

# 29. No External Intelligence Collection

Do NOT implement:

* trend scraping
* Facebook API
* Instagram API
* competitor scraping
* social listening
* external trend providers

Day 7 consumes existing structured signals.

Creating the intelligence ingestion system belongs to separate development work.

---

# 30. No Content Generation

Do NOT implement:

* captions
* scripts
* images
* videos
* UGC assets
* Blitz content
* Remix content
* ContentBrief

The output of Day 7 is:

```text
ContentOpportunity
```

Nothing beyond that.

---

# 31. Architecture After Day 7

The backend should conceptually support:

```text
Workspace
    ↓
ContentProfile
    │
    ├── Brand Intelligence
    ├── Audience Intelligence
    ├── Market Intelligence
    │       ↓
    │   MarketSignal
    │       ↓
    │   ContentOpportunity
    │
    └── Performance Intelligence
```

The strategic flow is:

```text
Intelligence
     ↓
Signal
     ↓
Opportunity
```

The next strategic stage will eventually be:

```text
ContentOpportunity
     ↓
ContentBrief
```

But ContentBrief is NOT part of Day 7.

---

# 32. Definition of Done

Day 7 is complete when:

* ContentOpportunity model exists
* database migration exists
* repository exists
* service exists
* scoring component exists
* schemas exist
* API endpoints exist
* filtering works
* sorting works
* priority calculation works
* strategic rationale works
* MarketSignal relationship works
* workspace isolation works
* creator without BusinessContext works
* business profile works
* tests exist
* existing tests still pass
* Ruff passes
* formatting passes
* migration validation passes

And:

```text
MarketSignal
    ↓
Opportunity Evaluation
    ↓
ContentOpportunity
```

is clearly preserved.

---

# 33. Explicit Out-of-Scope

The following are NOT part of Day 7:

* ContentBrief
* ContentItem
* Asset
* Publishing
* Performance Intelligence
* Learning Engine
* AI generation
* LLM integration
* social media integrations
* trend scraping
* competitor scraping
* vector database
* event bus
* microservices
* Docker
* Kubernetes
* Kafka
* background workers
* speculative infrastructure

Keep Day 7 focused on the **Content Opportunity Engine**.
