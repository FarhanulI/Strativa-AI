# Day 09 — Performance Intelligence v1 + Social Data Integration Architecture

## 1. Day 09 Goal

Build the first version of **Performance Intelligence**.

The system must be able to:

1. Store content performance data.
2. Calculate deterministic performance metrics.
3. Compare content against the profile's historical baseline.
4. Identify winning and underperforming patterns.
5. Use Gemini as an LLM reasoning layer.
6. Generate structured Performance Insights.
7. Convert performance learnings into strategic inputs.
8. Support `performance_gap` Content Opportunities.
9. Prepare the architecture for future Facebook, Instagram, TikTok, YouTube, and other social-media integrations.

Day 09 must NOT become a generic analytics dashboard.

The primary question is:

> **"What did this profile's content performance teach us, and what should we do next?"**

---

# 2. Product Architecture

The product follows:

```text
Understand
    ↓
Decide
    ↓
Brief
    ↓
Create
    ↓
Publish
    ↓
Measure
    ↓
Learn
    ↓
Understand
```

Day 09 primarily implements:

```text
Measure
   ↓
Understand
   ↓
Learn
```

---

# 3. Intelligence Architecture

The current intelligence system becomes:

```text
ContentProfile
      │
      ├── Brand Intelligence
      │
      ├── Audience Intelligence
      │      └── AudienceSignal
      │
      ├── Market Intelligence
      │      └── MarketSignal
      │
      └── Performance Intelligence
             │
             ├── ContentPerformance
             │
             ├── PerformanceAnalysis
             │
             └── PerformanceInsight
```

These intelligence sources eventually feed:

```text
Market Intelligence
        +
Audience Intelligence
        +
Performance Intelligence
        +
Brand/Profile Intelligence
        ↓
Opportunity Engine
        ↓
ContentOpportunity
        ↓
ContentBrief
        ↓
Creation
```

---

# 4. Critical Product Principle

Performance Intelligence is NOT the same thing as analytics.

Analytics answers:

```text
How many views did this post receive?
How many likes?
How many shares?
How much retention?
```

Performance Intelligence answers:

```text
Why did this post outperform?
Why did this post underperform?
What pattern does this reveal?
What should we repeat?
What should we stop?
What should we test next?
```

The system must therefore transform:

```text
Raw Performance
      ↓
Deterministic Analysis
      ↓
Evidence
      ↓
LLM Reasoning
      ↓
Performance Insight
      ↓
Strategic Learning
```

---

# 5. Social Media Integration Principle

The product will eventually integrate external social-media platforms.

Potential platforms:

```text
Facebook
Instagram
TikTok
YouTube
LinkedIn
X
```

However:

**Do NOT implement external social APIs in Day 09.**

Instead, Day 09 must create the internal architecture that allows external platforms to feed normalized data into the system later.

The core rule is:

```text
External Platform
      ↓
Platform Adapter
      ↓
Normalization
      ↓
Internal Content/Performance Models
      ↓
Performance Intelligence
```

Performance Intelligence must never depend directly on Instagram/Facebook/TikTok-specific API response formats.

---

# 6. Two Sources of Performance Data

The system must support two future sources.

## A. Platform-created content

Content is created inside the platform:

```text
Creation Engine
      ↓
Content Item
      ↓
Publishing
      ↓
External Platform
      ↓
External Post
      ↓
Performance Data
```

## B. Existing external content

A user already has content on social media:

```text
User's Instagram/Facebook
        ↓
OAuth Connection
        ↓
Historical Content Import
        ↓
External Posts
        ↓
Performance Data
        ↓
Performance Intelligence
```

This second flow is important for onboarding.

A creator should eventually be able to connect their account and allow the system to learn from their existing content.

---

# 7. Social Integration Architecture

Prepare the backend for:

```text
                Social Platforms
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   Facebook        Instagram       TikTok
     Adapter         Adapter        Adapter
        │              │              │
        └──────────────┼──────────────┘
                       ↓
               Normalization Layer
                       ↓
              Internal Data Models
                       ↓
             Performance Intelligence
```

Do NOT implement the actual adapters yet.

Create interfaces/contracts that future adapters will implement.

---

# 8. External Platform Adapter

Create a conceptual abstraction such as:

```python
class SocialPlatformAdapter(Protocol):
    ...
```

The abstraction should eventually support:

```text
fetch_posts()
fetch_post()
fetch_metrics()
```

Potential future methods:

```text
connect()
refresh_token()
disconnect()
fetch_profile()
fetch_posts()
fetch_post_metrics()
```

For Day 09, only define the architecture/interface where appropriate.

Do not implement real OAuth.

Do not implement real API requests.

---

# 9. Normalization Principle

External APIs use different terminology.

For example:

```text
Instagram:
shares
saves
reach

Facebook:
shares
reactions
reach

YouTube:
likes
comments
views
watch time
```

The application should normalize common concepts into internal models.

Example:

```text
External API
      ↓
Platform Adapter
      ↓
Normalized Performance Data
      ↓
ContentPerformance
```

Performance Intelligence should work against:

```text
ContentPerformance
```

and never directly against:

```text
InstagramResponse
FacebookInsightsResponse
TikTokAnalyticsResponse
```

---

# 10. ContentPerformance Model

Create:

```text
ContentPerformance
```

Conceptual structure:

```text
ContentPerformance
------------------
id
profile_id
content_item_id
external_post_id
platform
content_type
topic
format
hook
published_at

views
reach
impressions
likes
comments
shares
saves
clicks
conversions

watch_time_seconds
average_watch_time_seconds
completion_rate
retention_rate

metadata

created_at
updated_at
```

---

# 11. Important Relationship

`ContentPerformance` must belong to a `ContentProfile`.

Eventually it may also reference a `ContentItem`.

For Day 09:

```text
ContentProfile
      ↓
ContentPerformance
```

If the existing project already contains `ContentItem`, use an optional relationship:

```text
content_item_id: UUID | None
```

Do NOT force existing historical social content to have a ContentItem created by this application.

This is important because users may import content created outside the platform.

---

# 12. External Post ID

Use:

```text
external_post_id
```

to identify the original post on a social platform.

Examples:

```text
Instagram media ID
Facebook post ID
TikTok video ID
YouTube video ID
```

The field should remain nullable because manually entered performance data may not have an external ID.

---

# 13. Platform Field

Initial supported values:

```text
facebook
instagram
tiktok
youtube
linkedin
x
other
```

Keep the field extensible.

Do not create separate performance tables for every platform.

---

# 14. Content Type

Examples:

```text
post
reel
short_video
video
carousel
story
image
text
live
other
```

Do not over-constrain the database with platform-specific enums if the existing architecture favors extensible strings.

---

# 15. Performance Metrics

Recommended raw metrics:

```text
views
reach
impressions
likes
comments
shares
saves
clicks
conversions
watch_time_seconds
average_watch_time_seconds
completion_rate
retention_rate
```

Metrics should be nullable.

Different platforms expose different metrics.

---

# 16. Metric Validation

Count metrics:

```text
>= 0
```

Ratio metrics:

```text
0 <= value <= 1
```

Examples:

```text
completion_rate = 0.65
retention_rate = 0.72
```

Do not store:

```text
65
72
```

for these normalized ratios.

---

# 17. Derived Metrics

Calculate:

```text
engagement_rate
share_rate
save_rate
comment_rate
click_through_rate
conversion_rate
```

Use available denominator:

```text
reach
↓
views
↓
impressions
```

For engagement:

```text
likes + comments + shares + saves
```

Only calculate when a valid denominator exists.

---

# 18. ContentPerformanceService

Create:

```text
ContentPerformanceService
```

Responsibilities:

* CRUD
* validation
* profile ownership
* workspace isolation
* performance data management

It must NOT:

* calculate strategic insights
* call Gemini
* generate opportunities
* directly call social APIs

---

# 19. ContentPerformanceRepository

Create:

```text
ContentPerformanceRepository
```

Responsibilities:

* database persistence
* filtering
* pagination
* retrieval
* update
* delete

Do not put business logic into repositories.

---

# 20. PerformanceAnalysis Model

Create:

```text
PerformanceAnalysis
```

Conceptual structure:

```text
PerformanceAnalysis
-------------------
id
profile_id
content_performance_id

engagement_rate
share_rate
save_rate
comment_rate
click_through_rate
conversion_rate

baseline_engagement_rate
baseline_share_rate
baseline_save_rate
baseline_retention_rate

relative_engagement
relative_shares
relative_saves
relative_retention

performance_classification

baseline_available
comparables_count

evidence

analysis_version

created_at
updated_at
```

---

# 21. Why Separate Raw Data and Analysis

Required architecture:

```text
ContentPerformance
      ↓
Raw platform/content observations
```

```text
PerformanceAnalysis
      ↓
Deterministic calculations
```

```text
PerformanceInsight
      ↓
LLM interpretation and strategic learning
```

Never overwrite raw performance data with calculated intelligence.

---

# 22. Performance Baseline

Performance must be relative to the profile.

Do NOT compare profiles directly in Day 09.

Example:

```text
Profile A:
10,000 followers
5,000 views

Profile B:
1,000,000 followers
20,000 views
```

The raw numbers don't tell us enough.

The system should primarily compare content against:

```text
the same profile's historical performance
```

---

# 23. Baseline Calculation

Use the:

```text
median
```

rather than mean for the initial baseline.

This prevents viral outliers from disproportionately affecting the baseline.

---

# 24. Comparable Content

Preferred matching:

```text
same profile
+
same platform
+
same format
```

If insufficient:

```text
same profile
+
same platform
```

If still insufficient:

```text
same profile
```

Never use another profile's performance as the baseline.

---

# 25. Minimum Historical Sample

Minimum recommended:

```text
3 comparable content items
```

If fewer than 3 exist:

```json
{
  "baseline_available": false,
  "reason": "insufficient_history"
}
```

Do not fabricate a meaningful baseline.

---

# 26. Relative Metrics

Example:

```text
current share rate = 0.04
baseline share rate = 0.02
```

Then:

```text
relative_shares = 2.0
```

Meaning:

```text
2x profile baseline
```

Handle zero baselines safely.

---

# 27. Performance Classification

Initial deterministic classification:

```text
exceptional
strong
normal
weak
poor
```

Suggested thresholds:

```text
>= 1.75 → exceptional
>= 1.25 → strong
>= 0.80 → normal
>= 0.50 → weak
< 0.50  → poor
```

Use available relative metrics.

Do not rely blindly on a single metric when several are available.

---

# 28. Evidence

PerformanceAnalysis must produce structured evidence.

Example:

```json
{
  "baseline_available": true,
  "comparables_count": 14,
  "metrics": {
    "share_rate": {
      "current": 0.041,
      "baseline": 0.018,
      "relative": 2.28
    },
    "retention_rate": {
      "current": 0.67,
      "baseline": 0.48,
      "relative": 1.40
    }
  }
}
```

This evidence becomes the foundation for LLM reasoning.

---

# 29. PerformanceInsight Model

Create:

```text
PerformanceInsight
```

Conceptual structure:

```text
PerformanceInsight
------------------
id
profile_id
performance_analysis_id

insight_type
summary
likely_reason
strategic_learning
recommended_action

confidence_score

evidence

model_provider
model_name
prompt_version

status

created_at
updated_at
```

---

# 30. Insight Types

Initial:

```text
winning_pattern
performance_gap
creative_learning
format_learning
hook_learning
audience_learning
cta_learning
retention_learning
```

Keep extensible.

---

# 31. Gemini Integration

For the MVP, use:

```text
LLM Provider:
Google Gemini
```

Do not hard-code a model name into application logic.

Use configuration:

```env
LLM_PROVIDER=gemini
LLM_MODEL=<configured-gemini-model>
GEMINI_API_KEY=<your-api-key>
```

The exact Gemini model should remain configurable because free-tier model availability and limits may change.

---

# 32. LLM Provider Abstraction

Create:

```text
app/services/llm/
```

Recommended:

```text
llm/
├── base.py
├── provider.py
└── performance_reasoner.py
```

Concept:

```python
class LLMProvider(Protocol):

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ):
        ...
```

The rest of the application must not depend directly on the Gemini SDK.

---

# 33. Gemini Provider

Create:

```text
GeminiProvider
```

Responsibilities:

* Gemini API communication
* structured response handling
* provider-specific implementation
* provider errors

Do not put business logic here.

Do not calculate metrics here.

Do not calculate performance scores here.

---

# 34. PerformanceReasoner

Create:

```text
PerformanceReasoner
```

Responsibilities:

```text
PerformanceAnalysis
        +
Content metadata
        +
Profile context
        ↓
Gemini
        ↓
Structured PerformanceInsight
```

The reasoner must not have unrestricted database access.

---

# 35. LLM Input

Provide structured evidence.

Example:

```json
{
  "profile": {
    "positioning": "Football creator explaining tactics simply",
    "topics": [
      "football",
      "tactics"
    ],
    "expertise": [
      "football tactics"
    ],
    "goals": [
      "growth",
      "authority"
    ]
  },
  "content": {
    "topic": "4-3-3 pressing structure",
    "format": "short_video",
    "hook": "You are misunderstanding how this press works"
  },
  "analysis": {
    "classification": "strong",
    "relative_shares": 2.1,
    "relative_retention": 1.6,
    "relative_engagement": 1.3
  }
}
```

---

# 36. LLM Instructions

The Gemini reasoning prompt must explicitly say:

```text
Only make claims supported by the provided evidence.

Do not invent metrics.

Do not invent audience demographics.

Do not claim causation when the evidence only shows correlation.

Use "likely", "suggests", "appears", or "may indicate"
when causation cannot be established.

Focus on reusable strategic learning.

Recommend an actionable next experiment.
```

---

# 37. Structured LLM Output

Use a Pydantic schema.

Example:

```python
class PerformanceInsightLLMResult(BaseModel):
    insight_type: str
    summary: str
    likely_reason: str
    strategic_learning: str
    recommended_action: str
    confidence_score: float
```

Validate:

```text
0 <= confidence_score <= 1
```

Never store uncontrolled raw LLM prose as the primary intelligence object.

---

# 38. Evidence-Grounded Insight

Example:

```text
Performance:
Shares = 2.1x baseline
Retention = 1.6x baseline
Engagement = 1.3x baseline
```

Gemini should produce something like:

```text
Summary:
Contrarian educational framing significantly outperformed the profile baseline.

Likely reason:
The opening created curiosity while promising a practical explanation.

Strategic learning:
Contrarian educational hooks appear effective for tactical football content.

Recommended action:
Test the same hook structure on another tactical misconception.
```

The model must not claim:

```text
"Your audience prefers this because they are 18-24."
```

unless demographic evidence was actually provided.

---

# 39. LLM Failure Isolation

Critical requirement:

```text
Raw Performance
      ↓
Performance Analysis
```

must work even if Gemini is unavailable.

If:

```text
Gemini API fails
```

then:

```text
ContentPerformance remains
PerformanceAnalysis remains
PerformanceInsight generation fails safely
```

Do not roll back valid deterministic analysis because Gemini failed.

---

# 40. LLM Configuration Failure

If Gemini credentials are missing:

```text
POST /performance/{id}/analyze
```

must still work.

But:

```text
POST /performance/{id}/insights
```

may return:

```text
503 Service Unavailable
```

with a safe error response.

Do not expose:

* API keys
* provider stack traces
* internal SDK exceptions
* raw prompts

---

# 41. Prompt Versioning

Store:

```text
model_provider
model_name
prompt_version
```

Initial:

```text
prompt_version = performance_insight_v1
```

This will allow future comparison of different reasoning prompts.

---

# 42. Performance Analysis API

Create:

```http
POST /api/v1/profiles/{profile_id}/performance
```

```http
GET /api/v1/profiles/{profile_id}/performance
```

```http
GET /api/v1/profiles/{profile_id}/performance/{performance_id}
```

```http
PATCH /api/v1/profiles/{profile_id}/performance/{performance_id}
```

```http
DELETE /api/v1/profiles/{profile_id}/performance/{performance_id}
```

---

# 43. Analyze API

Create:

```http
POST /api/v1/profiles/{profile_id}/performance/{performance_id}/analyze
```

This endpoint:

```text
ContentPerformance
      ↓
PerformanceAnalysisService
      ↓
PerformanceAnalysis
```

must not require Gemini.

---

# 44. Generate Insight API

Create:

```http
POST /api/v1/profiles/{profile_id}/performance/{performance_id}/insights
```

Flow:

```text
ContentPerformance
      ↓
PerformanceAnalysis
      ↓
PerformanceReasoner
      ↓
Gemini
      ↓
PerformanceInsight
```

If analysis does not exist:

```text
run deterministic analysis first
```

Then generate the insight.

---

# 45. Insight Retrieval APIs

Create:

```http
GET /api/v1/profiles/{profile_id}/performance/{performance_id}/insights
```

and:

```http
GET /api/v1/profiles/{profile_id}/performance-insights
```

Support filters:

```text
insight_type
status
minimum_confidence
```

---

# 46. Opportunity Engine Integration

Existing `ContentOpportunity` must support:

```text
source_signal = performance_gap
```

For this source:

```text
performance_insight_id
```

must be available.

Concept:

```text
PerformanceInsight
       ↓
ContentOpportunity
```

Do NOT create a new Opportunity Engine.

Reuse the existing Opportunity Engine and OpportunityScorer.

---

# 47. Opportunity Relationship

The relationship becomes:

```text
MarketSignal
     ↓
ContentOpportunity

AudienceSignal
     ↓
ContentOpportunity

PerformanceInsight
     ↓
ContentOpportunity
```

Only one source relationship should be active for an opportunity.

---

# 48. Performance Gap Opportunity Example

Performance insight:

```text
Short tactical videos generate:
2.1x shares
1.6x retention
```

Opportunity:

```text
source_signal:
performance_gap

recommended_format:
short_video

target_objective:
growth
```

Strategic rationale:

```text
Short tactical videos have consistently exceeded this profile's
historical share and retention baselines, suggesting that concise
tactical explanations are a strong format to test again.
```

---

# 49. Opportunity Scoring

Do NOT create another scoring engine.

Reuse:

```text
OpportunityScorer
```

Performance insight signal strength may use:

```text
PerformanceInsight.confidence_score
```

Existing scoring architecture should remain the source of truth.

---

# 50. Profile Relevance

Performance opportunities must remain profile-specific.

Use:

```text
ContentPerformance.topic
+
ContentProfile.identity.topics
+
ContentProfile.identity.expertise
```

Initial deterministic matching:

```text
exact match → 1.0
related match → 0.8
unclear match → 0.5
```

Do not introduce embeddings yet.

---

# 51. Strategic Learning

`strategic_learning` is the reusable knowledge generated from performance.

Example:

```text
"Contrarian educational hooks appear particularly effective
for tactical football explanations."
```

This is more important than:

```text
"This Reel received 8,000 likes."
```

The first is reusable intelligence.

The second is raw observation.

---

# 52. Future Learning Architecture

Day 09 should NOT build a full Learning Engine.

For now:

```text
PerformanceInsight.strategic_learning
```

is the first persistent form of strategic learning.

Future days can aggregate repeated insights into long-term profile intelligence.

---

# 53. Future Social Account Model

Do not fully implement this in Day 09.

But architecture should anticipate a future model such as:

```text
SocialConnection
----------------
id
profile_id
platform
external_account_id
account_name
access_token_reference
refresh_token_reference
token_expires_at
status
created_at
updated_at
```

IMPORTANT:

Tokens must never be stored as plain text if the production architecture later requires encrypted credential storage.

For Day 09:

**Do not create OAuth or token storage unless already required by the current project architecture.**

---

# 54. Future Social Post Model

The architecture should anticipate:

```text
SocialPost
----------
id
profile_id
social_connection_id
platform
external_post_id
content_type
published_at
content_url
caption
metadata
```

This model may be introduced when Publishing/Social Integration is implemented.

Do NOT implement it fully in Day 09 unless an existing model already requires it.

---

# 55. Why ContentPerformance Must Remain Independent

A user may have:

```text
Instagram post
```

that was created before using the application.

Therefore:

```text
ContentPerformance
```

must not require:

```text
ContentItem
```

for all records.

Support:

```text
content_item_id = nullable
```

This allows both:

```text
Platform-created content
```

and:

```text
Imported historical content
```

to enter Performance Intelligence.

---

# 56. Historical Content Import — Future

Eventually onboarding can become:

```text
Connect Instagram
        ↓
Fetch historical posts
        ↓
Fetch available performance metrics
        ↓
Normalize
        ↓
ContentPerformance
        ↓
PerformanceAnalysis
        ↓
PerformanceInsight
        ↓
Initial Profile Intelligence
```

This is explicitly **future scope**.

---

# 57. Automatic Performance Sync — Future

Eventually:

```text
Social Platform
       ↓
Scheduled Sync
       ↓
New Metrics
       ↓
ContentPerformance
       ↓
PerformanceAnalysis
       ↓
PerformanceInsight
```

Do NOT implement scheduled jobs in Day 09.

Do NOT add Celery.

Do NOT add Kafka.

Do NOT add RabbitMQ.

Do NOT add microservices.

---

# 58. API Isolation

Every performance API must enforce:

```text
workspace
+
profile
```

ownership.

Cross-workspace:

```text
404
```

Cross-profile:

```text
404
```

Do not expose whether another workspace/profile owns the requested resource.

---

# 59. Database Relationships

Target:

```text
Workspace
   ↓
ContentProfile
   │
   ├── MarketSignal
   │       ↓
   │   ContentOpportunity
   │
   ├── AudienceSignal
   │       ↓
   │   ContentOpportunity
   │
   └── ContentPerformance
           ↓
      PerformanceAnalysis
           ↓
      PerformanceInsight
           ↓
      ContentOpportunity
```

---

# 60. Cascade Rules

Recommended:

```text
ContentProfile
    ↓
ContentPerformance
    CASCADE
```

```text
ContentPerformance
    ↓
PerformanceAnalysis
    CASCADE
```

```text
PerformanceAnalysis
    ↓
PerformanceInsight
    CASCADE
```

```text
PerformanceInsight
    ↓
ContentOpportunity
    SET NULL
```

Follow existing project conventions if they differ.

---

# 61. Indexes

ContentPerformance:

```text
profile_id
platform
format
topic
published_at
created_at
external_post_id
```

PerformanceAnalysis:

```text
profile_id
content_performance_id
performance_classification
created_at
```

PerformanceInsight:

```text
profile_id
performance_analysis_id
insight_type
confidence_score
status
created_at
```

ContentOpportunity:

```text
performance_insight_id
```

---

# 62. Schemas

Create:

```text
ContentPerformanceCreate
ContentPerformanceUpdate
ContentPerformanceResponse

PerformanceAnalysisResponse

PerformanceInsightResponse
PerformanceInsightLLMResult
```

Server-controlled fields must not be client-controlled.

Examples:

```text
id
profile_id
analysis_version
model_provider
model_name
prompt_version
created_at
updated_at
```

---

# 63. Repository Architecture

Maintain:

```text
Router
   ↓
Service
   ↓
Repository
   ↓
SQLAlchemy
   ↓
PostgreSQL
```

Repositories must not contain:

```text
LLM calls
performance scoring
strategic reasoning
opportunity decisions
```

---

# 64. Service Architecture

Recommended:

```text
ContentPerformanceService
PerformanceAnalysisService
PerformanceInsightService
PerformanceReasoner
```

Clear responsibility boundaries are required.

---

# 65. Testing — Raw Performance

Test:

* create
* retrieve
* list
* update
* delete
* invalid negative metrics
* invalid ratios
* optional metrics
* creator profile
* business profile
* profile without BusinessContext

---

# 66. Testing — Derived Metrics

Test:

```text
engagement_rate
share_rate
save_rate
comment_rate
click_through_rate
conversion_rate
```

Test:

```text
reach available
views fallback
impressions fallback
no denominator
zero denominator
```

---

# 67. Testing — Baselines

Test:

* same profile
* same platform
* same format
* fallback platform
* fallback profile
* insufficient history
* median calculation
* outlier behavior

---

# 68. Testing — Relative Performance

Test:

```text
2x baseline
1x baseline
0.5x baseline
zero baseline
missing baseline
```

---

# 69. Testing — Classification

Test:

```text
exceptional
strong
normal
weak
poor
```

Verify classification is deterministic.

---

# 70. Testing — LLM

Never use the real Gemini API in normal automated tests.

Mock:

```text
GeminiProvider
```

Test:

* valid structured response
* invalid response
* schema validation failure
* timeout
* provider unavailable
* confidence outside 0–1
* provider exception
* insight persistence
* model metadata
* prompt version

---

# 71. Testing — LLM Independence

Critical:

```text
Gemini unavailable
```

must not break:

```text
POST /performance/{id}/analyze
```

Deterministic analysis must still succeed.

---

# 72. Testing — Social Adapter Architecture

Since real integrations are not implemented yet, test the abstraction.

Verify that a mock adapter can conceptually provide:

```text
external post ID
platform
published date
content type
performance metrics
```

and that those values can eventually be normalized into `ContentPerformance`.

Do not call real social APIs.

---

# 73. Testing — Performance Opportunity

Test:

```text
source_signal = performance_gap
```

with:

```text
valid performance_insight_id
```

Verify:

* profile ownership
* workspace ownership
* score
* priority
* rationale
* source metadata

---

# 74. Testing — Cross-Profile Security

Verify:

```text
Profile A
cannot access
Profile B performance
```

Expected:

```text
404
```

Test:

* GET
* PATCH
* DELETE
* analyze
* generate insight
* opportunity creation

---

# 75. Regression Testing

All previous intelligence functionality must continue to work.

Test:

```text
MarketSignal
AudienceSignal
ContentOpportunity
OpportunityScorer
workspace isolation
profile isolation
```

Day 09 is additive.

It must not break Day 07 or Day 08.

---

# 76. Migration

Create Alembic migration for:

```text
content_performance
performance_analysis
performance_insight
```

Extend:

```text
content_opportunity
```

with:

```text
performance_insight_id
```

Migration must include:

* foreign keys
* indexes
* constraints
* nullable behavior
* cascade behavior
* downgrade path

---

# 77. Code Quality

Use the existing project tooling.

Run:

```bash
uv run pytest
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check .
```

Run the project's existing Alembic validation/migration workflow.

Do NOT introduce:

```text
Docker
Kubernetes
Kafka
RabbitMQ
Celery
microservices
```

---

# 78. Explicitly Out of Scope

Do NOT implement:

```text
Facebook OAuth
Instagram OAuth
TikTok OAuth
YouTube OAuth

Facebook Graph API
Instagram Graph API
TikTok API
YouTube API

social account connection UI
token refresh system
scheduled metric synchronization
webhooks
historical social import
automatic social polling

ContentBrief
Asset generation
Publishing Engine
full Learning Engine
experimentation engine
embeddings
vector database
semantic search
multi-agent architecture
microservices
```

The architecture should be ready for these capabilities later.

---

# 79. Future Social Integration Flow

The future architecture should become:

```text
User
  ↓
Connect Social Account
  ↓
OAuth
  ↓
SocialConnection
  ↓
Platform Adapter
  ↓
Fetch External Posts
  ↓
SocialPost
  ↓
Normalize
  ↓
ContentPerformance
  ↓
PerformanceAnalysis
  ↓
PerformanceInsight
  ↓
Strategic Learning
  ↓
Content Intelligence
```

---

# 80. Future Publishing Flow

Eventually:

```text
ContentBrief
      ↓
Creation Engine
      ↓
ContentItem
      ↓
Asset
      ↓
Publishing
      ↓
Social Platform
      ↓
External Post
      ↓
SocialPost
      ↓
Performance
```

This means content created inside the platform can be directly connected to its eventual performance.

---

# 81. Future Historical Learning Flow

For an existing creator:

```text
Connect Instagram
      ↓
Import historical content
      ↓
Normalize posts
      ↓
PerformanceAnalysis
      ↓
Gemini reasoning
      ↓
PerformanceInsight
      ↓
Profile Intelligence
```

This allows the product to understand the creator **before they create their first new post inside the platform**.

---

# 82. Creator Support

Performance Intelligence must work equally for:

```text
business
creator
personal_brand
expert
coach
startup
local_business
ecommerce_brand
```

Do NOT require:

```text
products
services
offers
commercial objectives
```

for creators.

A creator may only have:

```text
topics
expertise
positioning
audience
goals
```

and still receive performance intelligence.

---

# 83. Example — Creator

Profile:

```text
Type:
creator

Topic:
football

Goal:
grow Instagram page

Expertise:
football tactics
```

Performance:

```text
Format:
short video

Hook:
"You are misunderstanding this formation."

Shares:
2.1x baseline

Retention:
1.6x baseline
```

Performance Insight:

```text
Contrarian educational hooks appear particularly effective
for this creator's tactical football content.
```

Future Opportunity:

```text
Create another short tactical video
using a contrarian hook.
```

---

# 84. Example — Funny Content Creator

Profile:

```text
Type:
creator

Theme:
funny football content

Goal:
grow Facebook and Instagram
```

Performance:

```text
Format:
meme/reel

Topic:
football referee jokes

Shares:
2.5x baseline

Comments:
1.8x baseline
```

Insight:

```text
Relatable football humor generates significantly higher
sharing behavior for this profile.
```

Learning:

```text
Relatable football situations appear to be a strong
share-driving content pattern.
```

Opportunity:

```text
Create another relatable football situation using
the same comedic structure.
```

This demonstrates that Performance Intelligence is not only for businesses.

---

# 85. Example — Business

Profile:

```text
Type:
business

Positioning:
Affordable premium sportswear

Goal:
sales
```

Performance:

```text
Format:
UGC Reel

Product:
running shoes

Conversions:
1.8x baseline
```

Insight:

```text
UGC demonstrations outperform product-only presentations
for conversion-oriented content.
```

Future Opportunity:

```text
Test another UGC product demonstration with a stronger CTA.
```

The same Strategy Engine works.

---

# 86. Definition of Done

Day 09 is complete when:

* [ ] ContentPerformance model exists
* [ ] ContentPerformance supports external_post_id
* [ ] ContentPerformance optionally supports content_item_id
* [ ] PerformanceAnalysis exists
* [ ] PerformanceInsight exists
* [ ] Alembic migration exists
* [ ] CRUD APIs exist
* [ ] deterministic metric calculations work
* [ ] profile baselines work
* [ ] median comparison works
* [ ] relative performance works
* [ ] performance classification works
* [ ] structured evidence is generated
* [ ] Gemini provider abstraction exists
* [ ] Gemini model is configurable
* [ ] PerformanceReasoner exists
* [ ] structured LLM response validation works
* [ ] prompt version is stored
* [ ] provider/model metadata is stored
* [ ] LLM failures are isolated
* [ ] deterministic analysis works without Gemini
* [ ] PerformanceInsight can be generated
* [ ] performance_gap opportunity integration works
* [ ] existing OpportunityScorer is reused
* [ ] workspace isolation works
* [ ] profile isolation works
* [ ] creator profiles work
* [ ] business profiles work
* [ ] existing MarketSignal functionality still works
* [ ] existing AudienceSignal functionality still works
* [ ] social adapter abstraction exists
* [ ] no real external API integration is implemented yet
* [ ] tests pass
* [ ] Ruff passes
* [ ] formatting passes
* [ ] migration passes

---

# 87. Final Day 09 Architecture

The resulting architecture should be:

```text
                    CONTENT PROFILE
                          │
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
      Brand            Audience           Market
    Intelligence     Intelligence      Intelligence
                          │                 │
                          ↓                 ↓
                   AudienceSignal      MarketSignal
                          │                 │
                          └────────┬────────┘
                                   │
                                   ↓
                           OPPORTUNITY ENGINE
                                   ↑
                                   │
                         PerformanceInsight
                                   ↑
                                   │
                         Gemini Reasoning
                                   ↑
                                   │
                        PerformanceAnalysis
                                   ↑
                                   │
                         ContentPerformance
                                   ↑
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
             Manual/Internal              Future Social APIs
                Performance                       │
                    │                    ┌────────┼────────┐
                    │                    ↓        ↓        ↓
                    │                 Facebook Instagram TikTok
                    │                    │        │        │
                    │                    └────────┼────────┘
                    │                             ↓
                    │                       Normalization
                    │                             │
                    └─────────────────────────────┘
                                  ↓
                         ContentPerformance
```

The most important rule is:

```text
External APIs are DATA SOURCES.
They are NOT the intelligence layer.
```

And:

```text
Gemini is the REASONING layer.
It is NOT the source of truth for metrics.
```

Therefore:

```text
Social Data
    ↓
Deterministic Analysis
    ↓
Evidence
    ↓
Gemini Reasoning
    ↓
Performance Intelligence
    ↓
Strategic Learning
    ↓
Opportunity
    ↓
Content Brief
    ↓
Creation
```

This architecture preserves the central product principle:

> **The platform does not merely tell users how their content performed. It learns what works for them and uses those learnings to decide what they should create next.**
