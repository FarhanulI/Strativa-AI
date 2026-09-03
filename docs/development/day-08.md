# Day 8 — Audience Intelligence & Audience Signals

## Status

Planned

## Objective

Implement the first version of **Audience Intelligence focused on audience questions and content needs**.

Day 8 extends the existing Content Intelligence layer so that the Opportunity Engine can create strategic opportunities from audience-driven signals, not only market/trend signals.

The core flow becomes:

```text
ContentProfile
      │
      ├── Market Intelligence
      │       ↓
      │   MarketSignal
      │
      └── Audience Intelligence
              ↓
          AudienceSignal
              ↓
      Opportunity Evaluation
              ↓
      ContentOpportunity
```

The primary objective is to support this strategic source:

```text
audience_question
```

as a first-class opportunity source.

Day 8 does NOT implement ContentBrief.

---

# 1. Product Principle

The product should not only ask:

> "What is trending?"

It must also ask:

> "What does this audience currently want to know, understand, solve, or discuss?"

Audience Intelligence therefore becomes one of the inputs into Content Strategy.

The strategic flow is:

```text
Audience Question
+
ContentProfile
+
Audience Context
+
Profile Goals
+
Existing Intelligence
        ↓
Opportunity Evaluation
        ↓
ContentOpportunity
```

Do not directly generate content from an audience question.

The question must first become a strategically evaluated `ContentOpportunity`.

---

# 2. Universal Profile Support

Audience Intelligence must work for every ContentProfile type.

Supported examples:

```text
creator
business
personal_brand
expert
coach
startup
local_business
ecommerce_brand
```

Do NOT create separate audience models for creators and businesses.

Use the universal profile architecture:

```text
ContentProfile
      ↓
Audience Intelligence
      ↓
AudienceSignal
```

---

# 3. BusinessContext Remains Optional

BusinessContext must remain optional.

A creator should be able to have:

```text
ContentProfile
+
Audience Intelligence
+
Audience Signals
+
Content Opportunities
```

without:

```text
BusinessContext
Products
Services
Offers
```

Do not introduce any dependency from AudienceSignal to BusinessContext.

Business context may later improve audience interpretation, but it is not required.

---

# 4. Audience Intelligence Scope

Day 8 implements the first foundational audience intelligence capability:

## Audience Questions

The system should represent questions, problems, interests, or topics expressed by an audience.

Examples:

### Sports Creator

```text
Question:

"Why does a team use a high defensive line?"

Topic:

football tactics
```

### Photography Creator

```text
Question:

"How can I take better photos in low light?"

Topic:

photography
```

### Fitness Creator

```text
Question:

"How many days per week should a beginner train?"

Topic:

beginner fitness
```

### Comedy Creator

```text
Audience observation:

"People are heavily engaging with relatable gym situations."

Topic:

gym humor
```

### Business

```text
Question:

"Which running shoes are best for beginners?"

Topic:

running shoes
```

All of these must use the same audience intelligence architecture.

---

# 5. AudienceSignal Domain Model

Create:

```text
AudienceSignal
```

Conceptually:

```text
ContentProfile
      │
      │ 1:N
      ▼
AudienceSignal
```

Recommended fields:

```text
id
profile_id
signal_type
question
topic
description
intent
strength_score
status
source
metadata
observed_at
expires_at
created_at
updated_at
```

Use the project's established:

* UUID conventions
* timestamp conventions
* enum conventions
* SQLAlchemy conventions

Do not introduce new conventions if existing ones are already established.

---

# 6. Signal Type

Initial supported signal type:

```text
question
```

Design the enum so future values can be added.

Potential future values may include:

```text
question
pain_point
desire
objection
conversation
feedback
```

Do NOT implement those future types yet unless the existing architecture requires them.

Day 8 focuses on:

```text
question
```

---

# 7. Intent

Audience questions should have a simple intent classification.

Initial supported intents:

```text
learn
compare
solve
discover
validate
entertain
```

Examples:

```text
"How does offside work?"
→ learn

"Which camera is better for portraits?"
→ compare

"How do I fix blurry night photos?"
→ solve

"What are the best football boots?"
→ discover

"Is this workout actually effective?"
→ validate

"Give me funny football situations."
→ entertain
```

This is structured metadata.

Do NOT use an LLM to classify intent in Day 8.

---

# 8. Strength Score

Each AudienceSignal should have a normalized:

```text
strength_score
```

Range:

```text
0.0 <= strength_score <= 1.0
```

Interpretation:

```text
0.0
→ extremely weak audience signal

1.0
→ extremely strong audience signal
```

The score represents how strongly the audience signal indicates a meaningful content opportunity.

Day 8 does not implement machine-learning scoring.

The initial score may be supplied by trusted ingestion/internal systems or defaulted according to the existing application convention.

Do not allow arbitrary values outside `[0, 1]`.

---

# 9. AudienceSignal Source

Represent where the audience signal originated.

Initial values:

```text
manual
```

The model should be extensible for future sources such as:

```text
comments
messages
search
social
analytics
survey
community
```

Do NOT implement external social integrations in Day 8.

For now, support:

```text
manual
```

---

# 10. AudienceSignal Status

Initial statuses:

```text
active
resolved
expired
archived
```

Default:

```text
active
```

Use the existing enum conventions.

---

# 11. AudienceSignal Lifecycle

The initial lifecycle is:

```text
Created
   ↓
Active
   ↓
Resolved / Expired / Archived
```

An active audience question can be used by the Opportunity Engine.

Resolved or archived questions should not automatically generate new opportunities.

Do not build an automated lifecycle worker in Day 8.

---

# 12. AudienceSignal → ContentOpportunity

Extend the existing Opportunity Engine.

Day 7 already supports:

```text
trend
performance_gap
audience_question
pillar_rotation
market_conversation
```

Day 8 makes:

```text
audience_question
```

a real source.

The relationship becomes:

```text
AudienceSignal
      ↓
Opportunity Evaluation
      ↓
ContentOpportunity
```

A ContentOpportunity should optionally reference:

```text
audience_signal_id
```

---

# 13. Opportunity Source Validation

The opportunity may originate from either:

```text
MarketSignal
```

or:

```text
AudienceSignal
```

or another supported future source.

Do NOT allow an opportunity to reference unrelated signals.

For an audience-derived opportunity:

```text
source_signal = audience_question
```

and:

```text
audience_signal_id != null
```

For a market-derived opportunity:

```text
source_signal = trend
```

or another market source.

The appropriate source relationship must be populated.

---

# 14. Cross-Profile Validation

When creating an opportunity from an AudienceSignal:

```text
AudienceSignal.profile_id
must equal
ContentOpportunity.profile_id
```

If not:

```text
404 Not Found
```

Do not expose the existence of another profile's signal.

---

# 15. Cross-Workspace Validation

Workspace isolation remains mandatory.

The ownership chain is:

```text
Workspace
    ↓
ContentProfile
    ↓
AudienceSignal
    ↓
ContentOpportunity
```

A user must never be able to create an opportunity for their profile using another workspace's AudienceSignal.

Return:

```text
404 Not Found
```

for cross-workspace access.

---

# 16. Opportunity Scoring Extension

Extend the Day 7 scoring engine.

For an audience-question opportunity:

```text
signal_strength
```

should be derived from:

```text
AudienceSignal.strength_score
```

instead of MarketSignal velocity/engagement.

Therefore:

```text
AudienceSignal
      ↓
strength_score
      ↓
OpportunityScorer
```

The remaining scoring components continue to use the Day 7 architecture:

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

Do NOT create a second scoring engine.

Extend the existing `OpportunityScorer`.

---

# 17. Profile Relevance for Audience Signals

For Day 8, profile relevance should be determined from the relationship between:

```text
AudienceSignal.topic
```

and:

```text
ContentProfile.identity.topics
ContentProfile.identity.expertise
```

Use a deterministic v1 approach.

Suggested scoring:

```text
Exact topic match:
1.0

Topic appears related to configured topics/expertise:
0.8

No clear match:
0.5
```

Keep the logic isolated.

Do not implement semantic embeddings.

Do not implement an LLM.

Do not build a machine-learning relevance model.

---

# 18. Goal Alignment

Reuse the Day 7 goal-alignment logic.

Do not duplicate the implementation.

If target objective matches a configured profile goal:

```text
1.0
```

If goals exist but there is no match:

```text
0.5
```

If goals are not configured:

```text
0.5
```

The scorer must remain shared.

---

# 19. Timeliness

Audience signals should support:

```text
observed_at
expires_at
```

Use the existing Day 7 timeliness calculation where possible.

Do not create a second timeliness algorithm.

If no expiration is available:

```text
0.5
```

If expired:

```text
0.0
```

Otherwise calculate a normalized active-signal timeliness score.

---

# 20. Strategic Rationale

Extend the existing rationale generator.

For an audience question, the rationale should explain:

1. what the audience is asking
2. why the question is relevant to this profile
3. what objective the opportunity supports

Example:

```text
The audience is actively seeking practical guidance on low-light
photography. This topic aligns strongly with the profile's
photography expertise and can support the authority objective.
```

The rationale must be generated from structured data.

Do NOT use an LLM.

Do NOT hard-code photography, football, fitness, comedy, or any other niche.

---

# 21. Recommended Format

Audience-question opportunities may recommend formats such as:

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

The format is a strategic recommendation.

Do not generate the actual content.

---

# 22. AudienceSignal API

Implement CRUD endpoints under the profile.

### Create

```http
POST /api/v1/profiles/{profile_id}/audience-signals
```

### List

```http
GET /api/v1/profiles/{profile_id}/audience-signals
```

Support filtering by:

```text
signal_type
intent
status
source
```

Support sorting by:

```text
strength_score
observed_at
```

Follow existing pagination conventions.

### Retrieve

```http
GET /api/v1/profiles/{profile_id}/audience-signals/{signal_id}
```

### Update

```http
PATCH /api/v1/profiles/{profile_id}/audience-signals/{signal_id}
```

### Delete

```http
DELETE /api/v1/profiles/{profile_id}/audience-signals/{signal_id}
```

---

# 23. Opportunity API Extension

Extend the existing ContentOpportunity API where required.

The create request may support:

```text
audience_signal_id
```

When:

```text
source_signal = audience_question
```

the service must validate that:

```text
audience_signal_id
```

is provided.

When:

```text
source_signal != audience_question
```

an unrelated AudienceSignal must not be accepted.

---

# 24. Schemas

Create:

```text
AudienceSignalCreate
AudienceSignalUpdate
AudienceSignalResponse
```

The server controls:

```text
id
profile_id
workspace ownership
created_at
updated_at
```

Validate:

```text
strength_score ∈ [0, 1]
```

Do not allow clients to submit server-controlled ownership information.

---

# 25. Repository

Create a dedicated AudienceSignal repository.

It should handle:

```text
create
get_by_id
list
update
delete
```

Filtering should remain in the repository/database layer.

Do not place business rules inside the repository.

---

# 26. Service

Create:

```text
AudienceSignalService
```

Responsibilities:

* validate ContentProfile ownership
* create signals
* retrieve signals
* update signals
* delete signals
* validate signal data
* enforce lifecycle rules

The Opportunity Service remains responsible for creating opportunities.

Do not move opportunity logic into AudienceSignalService.

---

# 27. Database Relationships

The intended relationships are:

```text
Workspace
   ↓
ContentProfile
   ├── MarketSignal
   │       ↓
   │   ContentOpportunity
   │
   └── AudienceSignal
           ↓
       ContentOpportunity
```

`AudienceSignal` belongs to one `ContentProfile`.

One `ContentProfile` can have many `AudienceSignal` records.

An AudienceSignal can optionally be referenced by ContentOpportunity.

---

# 28. Delete Behavior

When a ContentProfile is deleted:

```text
ContentProfile
    ↓
AudienceSignal
```

AudienceSignals should be deleted with the profile.

When an AudienceSignal is deleted:

```text
AudienceSignal
    ↓
ContentOpportunity
```

The opportunity should remain.

Therefore:

```text
audience_signal_id → SET NULL
```

The same principle already used for MarketSignal should be preserved.

---

# 29. Database Constraints and Indexes

Add appropriate constraints:

```text
0.0 <= strength_score <= 1.0
```

Add indexes for:

```text
profile_id
signal_type
intent
status
source
strength_score
observed_at
```

Do not create unnecessary indexes.

---

# 30. Tests — AudienceSignal

Test:

### CRUD

* create
* retrieve
* list
* update
* delete

### Validation

* valid strength score
* strength score below 0
* strength score above 1
* valid intent
* invalid intent
* valid signal type
* invalid signal type

### Workspace isolation

Workspace A cannot:

* retrieve Workspace B signal
* update Workspace B signal
* delete Workspace B signal

All should return:

```text
404
```

### Profile isolation

A signal belonging to Profile A cannot be accessed through Profile B.

---

# 31. Tests — Opportunity Integration

Test:

### Audience-derived opportunity

Create:

```text
AudienceSignal
```

Then create:

```text
ContentOpportunity
```

using:

```text
source_signal = audience_question
audience_signal_id = <signal>
```

Verify:

* relationship is correct
* score is calculated
* priority is calculated
* rationale is generated
* metadata contains scoring version/components

### Invalid relationship

Attempt:

```text
Profile A
    ↓
Opportunity
    ↓
AudienceSignal belonging to Profile B
```

Expected:

```text
404
```

### Creator

Verify that a creator without BusinessContext can create:

```text
AudienceSignal
→ ContentOpportunity
```

### Business

Verify the same flow for a business.

---

# 32. Scoring Tests

Verify audience signal strength is used:

```text
AudienceSignal.strength_score
```

Example:

```text
strength_score = 1.0
```

should result in:

```text
signal_strength = 1.0
```

Example:

```text
strength_score = 0.0
```

should result in:

```text
signal_strength = 0.0
```

Test mixed values.

Verify final opportunity score remains:

```text
0.0 <= opportunity_score <= 1.0
```

---

# 33. Profile Relevance Tests

Test:

```text
AudienceSignal.topic
```

against:

```text
ContentProfile.identity.topics
ContentProfile.identity.expertise
```

Verify:

```text
exact match → 1.0
related match → 0.8
no clear match → 0.5
```

Keep the test deterministic.

---

# 34. No AI Integration

Day 8 is still deterministic.

Do NOT implement:

* OpenAI
* Anthropic
* Gemini
* LLM classification
* embeddings
* vector databases
* semantic search
* AI agents

These may be introduced later.

---

# 35. No External Data Collection

Do NOT implement:

* Instagram comments ingestion
* Facebook comments ingestion
* social listening
* Reddit ingestion
* Google search integration
* surveys
* messaging integrations
* automatic audience scraping

Day 8 creates the internal domain foundation.

External ingestion can be added later.

---

# 36. No ContentBrief

Do NOT implement:

```text
ContentOpportunity
    ↓
ContentBrief
```

That belongs to a later development day.

Day 8 ends at:

```text
Audience Intelligence
    ↓
AudienceSignal
    ↓
ContentOpportunity
```

---

# 37. No New Strategy Engine

Do NOT create:

```text
AudienceStrategyEngine
```

There is only one:

```text
Content Strategy Engine
```

Audience signals are inputs to that engine.

---

# 38. Preserve Day 7

Day 8 must not break existing MarketSignal opportunities.

The following must continue working:

```text
MarketSignal
    ↓
ContentOpportunity
```

Day 8 adds:

```text
AudienceSignal
    ↓
ContentOpportunity
```

Both must use the same:

```text
OpportunityScorer
ContentOpportunityService
ContentOpportunityRepository
ContentOpportunity model
```

where appropriate.

---

# 39. Architecture After Day 8

The backend should now conceptually support:

```text
Workspace
    ↓
ContentProfile
    │
    ├── Brand Intelligence
    │
    ├── Audience Intelligence
    │       ↓
    │   AudienceSignal
    │
    ├── Market Intelligence
    │       ↓
    │   MarketSignal
    │
    └── Performance Intelligence
```

Both intelligence sources can feed:

```text
MarketSignal ──────┐
                    │
AudienceSignal ────┤
                    ↓
            Opportunity Engine
                    ↓
            ContentOpportunity
```

The strategic architecture is now:

```text
Content Intelligence
        ↓
    Signals
        ↓
Opportunity Evaluation
        ↓
ContentOpportunity
```

---

# 40. Definition of Done

Day 8 is complete when:

* AudienceSignal model exists
* database migration exists
* AudienceSignal repository exists
* AudienceSignal service exists
* schemas exist
* CRUD API exists
* validation works
* filtering works
* sorting works
* workspace isolation works
* profile isolation works
* audience-question opportunities can be created
* AudienceSignal can feed OpportunityScorer
* existing MarketSignal opportunities still work
* shared OpportunityScorer is preserved
* shared ContentOpportunity model is preserved
* creator without BusinessContext works
* business profile works
* strategic rationale works
* scoring metadata is stored
* tests pass
* Ruff passes
* formatting passes
* migration validation passes

---

# 41. Explicit Out-of-Scope

The following are NOT part of Day 8:

* ContentBrief
* ContentItem
* Asset
* Publishing
* Performance Intelligence
* Learning Engine
* LLM integration
* embeddings
* vector database
* social media ingestion
* social listening
* comment scraping
* Facebook API
* Instagram API
* Reddit API
* Google Search API
* automatic audience discovery
* AI agents
* microservices
* Docker
* Kubernetes
* Kafka
* event bus
* background workers
* speculative infrastructure

Keep Day 8 focused on **Audience Intelligence and Audience Signals**.

---

# 42. Final Product Principle

After Day 8, the system should understand two important types of strategic signals:

```text
WHAT IS HAPPENING IN THE MARKET?
        ↓
MarketSignal

WHAT DOES THE AUDIENCE WANT / ASK / CARE ABOUT?
        ↓
AudienceSignal
```

Both should flow into one strategy system:

```text
MarketSignal
       │
       ├──────────────┐
       │              │
AudienceSignal       │
       │              │
       └──────┬───────┘
              ↓
       Opportunity Engine
              ↓
      ContentOpportunity
```

This preserves the central product principle:

> The platform should decide what a specific profile should create next based on profile context, audience needs, market signals, goals, and eventually performance learnings—not simply generate content from whatever is trending.
