Day 11 — Content Brief Engine

Status

Planned

Objective

Implement the first version of the Content Brief Engine.

Day 11 introduces the strategic stage between an evaluated ContentOpportunity and the future content creation layer:

ContentOpportunity
        ↓
Brief Composition
        ↓
ContentBrief
        ↓
Future Content Creation

The strategic loop becomes:

Understand → Decide → BRIEF → Create → Publish → Measure → Learn

Day 11 stops at ContentBrief.

It does not implement content creation, final hooks, captions, scripts, assets, or publishing.

1. Product Purpose

A ContentBrief is the strategic contract that instructs the future creation stage.

It answers:

What should be created?
For whom?
Why?
On which platform?
In which format?
Which objective does it serve?
Which strategic angle / message should it use?
Which pain point / desire / question does it address?
What does success look like?

A brief is not:

a caption

a final hook

a script

an image

a video

an asset

a published post

a final CTA copy

an AI content-generation request

A brief is a strategic instruction.

2. Strategic Position

The architecture after Day 11 is:

Content Intelligence
        ↓
Content Strategy
        ↓
ContentOpportunity
        ↓
ContentBrief                 ← Day 11
        ↓
Future Content Creation
        ↓
Future Publishing
        ↓
Performance Intelligence
        ↓
Learning

A brief must remain traceable to:

ContentProfile
    ↓
Signal / Intelligence
    ↓
ContentOpportunity
    ↓
ContentBrief

Every brief belongs to exactly one opportunity.

Every opportunity may have zero or more briefs.

Do not allow a brief to exist without an opportunity.

3. Universal Profile Support

The Brief Engine works for every supported ContentProfile type:

creator
business
personal_brand
expert
coach
startup
local_business
ecommerce_brand

Do not create separate brief models.

Use one universal model:

ContentProfile
    ↓
ContentOpportunity
    ↓
ContentBrief

Do not create:

CreatorBrief
BusinessBrief
UGCBrief
VideoBrief
ImageBrief

Format and platform remain fields on the universal brief.

4. BusinessContext Remains Optional

The Brief Engine must work for creators and other non-commercial profiles without requiring:

BusinessContext
Products
Services
Offers

Business context may improve a brief when available, but it must never be required.

Do not introduce a hard dependency from ContentBrief to BusinessContext, Product, Service, or Offer.

5. ContentBrief Domain Model

Create a ContentBrief model.

Conceptually:

ContentProfile
      │ 1:N
      ▼
ContentOpportunity
      │ 1:N
      ▼
ContentBrief

Recommended fields:

id
profile_id
opportunity_id

title
core_message
angle
big_idea

strategic_rationale

target_objective

target_persona_id
target_pain_point_id
target_desire_id
target_audience_question_id

recommended_format
recommended_platform
recommended_length

tone
voice_guidelines

cta_strategy

key_points
supporting_context
success_criteria

brief_version
generation_source
status

metadata

created_at
updated_at

Use the project's established:

UUID conventions

timezone-aware timestamp conventions

enum conventions

SQLAlchemy patterns

metadata JSONB conventions

migration naming conventions

Do not introduce new conventions when established ones already exist.

6. Relationship Rules

The relationships are:

ContentProfile 1:N ContentBrief
ContentOpportunity 1:N ContentBrief

Optional references:

Persona
PainPoint
Desire
AudienceQuestion

Rules:

profile_id is required.

opportunity_id is required.

ContentBrief.profile_id MUST equal ContentOpportunity.profile_id.

Any optional intelligence reference must belong to the same profile.

Cross-profile references must return 404.

Cross-workspace references must return 404.

Do not expose the existence of another profile's or workspace's resources.

7. Target Objective

target_objective reuses the existing objective enum:

growth
authority
lead_gen
sales

Default behavior:

If omitted, inherit from ContentOpportunity.target_objective.

If supplied, allow a different objective only when it passes the same goal-alignment validation used by Day 7.

Do not restrict creator profiles to growth / authority.

Do not re-run opportunity scoring in Day 11.

8. Recommended Format

recommended_format is a free-form string consistent with the existing ContentOpportunity.recommended_format.

Examples:

reel
short_video
long_video
carousel
image
text_post
story
ugc
blitz
remix

Default:

Inherit from the parent opportunity when omitted.

Keep it a string rather than introducing a new enum.

This avoids premature format lock-in.

9. Recommended Platform

recommended_platform mirrors the values used by ContentPerformance.platform:

facebook
instagram
tiktok
youtube
linkedin
x
other

Default:

other

when no platform can be inferred.

Do not integrate with real social APIs in Day 11.

10. Recommended Length

Represent length as free-form guidance:

30-45s
2 minutes
6 slides

Store it as nullable string.

Do not enforce numeric duration in Day 11.

11. Brief Status

Initial statuses:

draft
ready
approved
archived

Default:

draft

Use the project's established enum pattern, matching OpportunityStatus.

Lifecycle:

draft → ready → approved
                      ↓
                  archived

Do not build an automated lifecycle worker.

Status transitions must be validated by the service.

12. Generation Source

Every brief records how it was produced.

Values:

manual
deterministic
ai_assisted

Semantics:

manual
→ Client intentionally supplies the strategic content.

deterministic
→ Server composes the brief from the opportunity and available intelligence
  without an AI call.

ai_assisted
→ Deterministic scaffold is enriched successfully through the AI Router.

generation_source is server-controlled.

Clients must never submit it.

Explicit composition mode

Do not infer "manual" merely by checking whether many nullable fields happen to be populated.

Use an explicit client-controlled intent:

composition_mode:
    compose
    manual

Recommended behavior:

composition_mode=compose + use_ai=false
    → deterministic

composition_mode=compose + use_ai=true
    → ai_assisted on successful enrichment
    → deterministic if AI enrichment fails

composition_mode=manual
    → manual

The server still owns generation_source.

13. Brief Version

Store:

brief_version = "v1"

as a top-level column.

This mirrors:

Day 7: scoring_version
Day 9: analysis_version / prompt_version

The top-level column makes future version comparisons possible without scanning JSONB.

14. Metadata

Use the existing metadata JSONB pattern.

Do not duplicate top-level server-controlled fields inside metadata.

Recommended shape:

{
  "composition": {
    "inherited_objective": true,
    "inherited_format": true,
    "signal_type": "audience_question",
    "source_signal_id": "...",
    "persona_id": null,
    "pain_point_id": null,
    "desire_id": null,
    "audience_question_id": "..."
  },
  "ai": {
    "provider": "gemini",
    "model": "<configured-model>",
    "prompt_version": "content_brief_v1"
  }
}

Keep these only as top-level columns:

brief_version
generation_source
status

The metadata should preserve enough composition lineage to understand why the brief was created.

Do not duplicate full source objects.

15. Composition Pipeline

The Brief Engine has two clearly separated stages.

Stage A — Deterministic Composition

Inputs:

ContentProfile

ContentOpportunity
    ├── source signal
    ├── target_objective
    ├── strategic_rationale
    └── recommended_format

Optional:
    persona
    pain point
    desire
    audience question

Output:

A minimally complete ContentBrief with:

title
core_message
strategic_rationale
target_objective
recommended_format
recommended_platform
tone
cta_strategy
key_points
success_criteria

Stage A must succeed even when the AI Router is unavailable.

Stage B — AI Enrichment

Uses the Day 10 AI Router:

BriefComposer
      ↓
AI Router
      ↓
AI Provider

Task:

AITask.CONTENT_CONCEPT_GENERATION

AI enrichment may populate or improve:

angle
big_idea
voice_guidelines
key_points
supporting_context

AI enrichment must never convert the brief into final creative content.

Stage B failure must never fail Stage A.

If Stage B fails:

generation_source = deterministic

and the valid deterministic brief remains persisted.

Do not roll back a valid deterministic brief because Gemini/provider enrichment failed.

16. Deterministic Composition Rules

Title

Default:

"{recommended_format} — {source_summary}"

source_summary is derived in this order:

1. MarketSignal.title / topic
2. AudienceSignal.question / topic
3. PerformanceInsight.summary
4. ContentOpportunity.title

depending on the opportunity source.

Core Message

Derive from:

ContentOpportunity.strategic_rationale

and truncate to one sentence.

Do not invent new strategic claims.

Strategic Rationale

Copy:

ContentOpportunity.strategic_rationale

verbatim.

Do not re-score the opportunity.

Tone

Default:

clear, confident, on-brand

when no brand voice is available.

If Brand Intelligence provides an established tone/voice, use that information rather than replacing it with a generic tone.

CTA Strategy

Use strategic CTA direction rather than final CTA copy.

Deterministic defaults:

growth
→ encourage sharing

authority
→ encourage saving / following

lead_gen
→ encourage conversation / DM

sales
→ encourage click / purchase

Store this as:

cta_strategy

Do not surface these defaults as literal final user-facing CTA copy.

The future Creation Engine converts CTA strategy into final wording.

Key Points

Populate exactly 3 deterministic points:

1. What the signal represents.
2. Why it is relevant to this profile.
3. Which objective it serves.

Success Criteria

Use strategic criteria such as:

audience remains engaged past the hook
audience takes the recommended CTA
content reinforces the profile's positioning

Do not invent numeric performance targets.

17. Strategic Angle Boundary

angle and big_idea are allowed in a brief because they are strategic direction.

They are not final creative wording.

For example:

Strategic angle:
Explain why defensive midfielders are becoming more
important in modern football.

Not:

Final hook:
"Everyone praises the striker — but THIS player won the game..."

Therefore:

angle = strategic framing
big_idea = strategic concept

The Creation Engine is responsible for turning these into final hooks, captions, scripts, and other creative execution.

18. AI Enrichment Rules

Reuse the Day 10 AI infrastructure:

BriefComposer
     ↓
AI Router
     ↓
AIProvider
     ↓
GeminiProvider

The composer:

must not import the Gemini SDK

must not call Gemini directly

must build structured input

must request a Pydantic-typed response

must reject malformed responses

must never persist uncontrolled raw LLM prose as primary brief content

Structured input should include only relevant information such as:

profile positioning
topics
expertise
brand voice
opportunity source
signal summary
target objective
recommended format
available audience context
available performance context

Prompt version:

content_brief_v1

The prompt must explicitly instruct:

Only use the provided profile and signal information.

Do not invent audience demographics.

Do not invent products or services.

Do not invent offers.

Do not fabricate performance data.

Do not invent statistics.

Do not use external facts.

Do not write final captions.

Do not write final hooks.

Do not write scripts.

Do not produce finished creative.

Produce strategic direction only.

19. Structured AI Response Schema

Create:

class BriefCompositionLLMResult(BaseModel):
    angle: str
    big_idea: str
    voice_guidelines: str
    key_points: list[str]
    supporting_context: list[str]

Rules:

every field is required

key_points maximum approximately 5 items

supporting_context maximum approximately 5 items

every item must be a string

validation failure means Stage B failure

malformed AI output must not be persisted

Supporting context rule

supporting_context must be derived only from supplied intelligence.

It must not become a place for invented evidence.

No:

invented statistics
invented studies
invented demographics
invented performance claims

If evidence is required in a future version, introduce structured source references rather than allowing uncontrolled factual claims.

20. BriefComposer

Create a dedicated service:

app/services/brief/composer.py

or the project's established equivalent.

Responsibilities:

accept structured composition inputs

execute Stage A deterministically

optionally execute Stage B through the AI Router

return a domain object / composition result

avoid persistence concerns

The composer must NOT:

access the database

touch repositories

call Gemini directly

import Gemini SDK

own opportunity scoring

own authorization

persist models

This mirrors the boundaries established by:

OpportunityScorer
PerformanceReasoner
AIRouter

21. ContentBriefRepository

Create a dedicated repository.

Responsibilities:

create
get_by_id
list
update
delete

Filtering:

opportunity_id
status
generation_source
target_objective
recommended_format
recommended_platform

Sorting:

created_at
updated_at

Do not put:

composition logic

AI logic

authorization logic

inside the repository.

22. ContentBriefService

Create a dedicated service.

Responsibilities:

validate workspace ownership

validate profile ownership

validate opportunity ownership

validate opportunity/profile match

validate optional persona ownership

validate optional pain point ownership

validate optional desire ownership

validate optional audience question ownership

invoke BriefComposer

persist through ContentBriefRepository

enforce status transitions

enforce server-controlled fields

preserve deterministic fallback when AI enrichment fails

Conceptually:

Router
   ↓
ContentBriefService
   ↓
BriefComposer
   ├── deterministic composition
   └── AIRouter → AIProvider
   ↓
ContentBriefRepository
   ↓
SQLAlchemy

23. Pydantic Schemas

Create:

ContentBriefCreate
ContentBriefUpdate
ContentBriefResponse

Recommended:

ContentBriefCompositionRequest

only if useful for internal/service separation.

Do not create a second public "compose" endpoint merely because a composition request schema exists.

Client-controlled create fields

opportunity_id

composition_mode        (optional, default "compose")
use_ai                  (optional bool, default false)

title                   (optional)
core_message            (optional)
angle                   (optional)
big_idea                (optional)

target_objective        (optional)

target_persona_id       (optional)
target_pain_point_id    (optional)
target_desire_id        (optional)
target_audience_question_id (optional)

recommended_format      (optional)
recommended_platform    (optional)
recommended_length      (optional)

tone                    (optional)
voice_guidelines        (optional)

cta_strategy            (optional)

key_points              (optional)
supporting_context      (optional)
success_criteria        (optional)

Server-controlled fields

id
profile_id
strategic_rationale
brief_version
generation_source
status
metadata
created_at
updated_at

Clients must never set:

brief_version
generation_source
metadata
strategic_rationale

Clients may not reassign:

profile_id
opportunity_id

after creation.

24. API Endpoints

Follow the existing hierarchical API pattern.

Create

POST /api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs

Behavior:

composition_mode=compose + use_ai=false
→ deterministic

composition_mode=compose + use_ai=true
→ ai_assisted if AI enrichment succeeds
→ deterministic if AI enrichment fails

composition_mode=manual
→ manual

No second public compose endpoint is required.

List briefs under an opportunity

GET /api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs

List all briefs for a profile

GET /api/v1/profiles/{profile_id}/briefs

Filters:

status
generation_source
target_objective
recommended_format
recommended_platform
opportunity_id

Sorting:

created_at
updated_at

Follow existing pagination conventions.

Retrieve

GET /api/v1/profiles/{profile_id}/briefs/{brief_id}

Update

PATCH /api/v1/profiles/{profile_id}/briefs/{brief_id}

Rules:

clients may edit strategic fields

clients may transition status following the lifecycle

clients may not overwrite brief_version

clients may not overwrite generation_source

clients may not overwrite metadata

clients may not overwrite strategic_rationale

clients may not reassign opportunity_id

clients may not reassign profile_id

Delete

DELETE /api/v1/profiles/{profile_id}/briefs/{brief_id}

25. Workspace Isolation

Authorization chain:

Workspace
    ↓
ContentProfile
    ↓
ContentOpportunity
    ↓
ContentBrief

Every operation must verify:

current_workspace
    owns
ContentProfile
    owns
ContentOpportunity
    owns
ContentBrief

Cross-workspace access must return:

404 Not Found

Do not expose whether another workspace's resource exists.

Reuse existing workspace-ownership helpers from Day 7–10.

Do not create a second ownership system.

26. Cross-Profile Validation

For every optional intelligence relationship:

Persona.profile_id
    == ContentBrief.profile_id

PainPoint.profile_id
    == ContentBrief.profile_id

Desire.profile_id
    == ContentBrief.profile_id

AudienceQuestion.profile_id
    == ContentBrief.profile_id

Mismatch:

404 Not Found

Do not return 400, because that may confirm that the resource exists.

Cross-workspace references must also return 404.

27. Delete Behavior

Recommended cascade behavior:

ContentProfile → ContentBrief
    CASCADE

ContentOpportunity → ContentBrief
    CASCADE

Persona / PainPoint / Desire / AudienceQuestion
    → ContentBrief
    SET NULL

Rationale:

a brief is meaningless without its opportunity

an intelligence reference may disappear without invalidating the brief

Follow established project conventions if they differ.

28. Database Constraints and Indexes

Constraints:

title                NOT NULL
core_message         NOT NULL
strategic_rationale  NOT NULL
target_objective     NOT NULL
status               NOT NULL
brief_version        NOT NULL
generation_source    NOT NULL

Nullable fields may remain nullable where explicitly designed.

Indexes:

profile_id
opportunity_id
status
target_objective
recommended_format
recommended_platform
generation_source
created_at

Composite indexes only where existing API access patterns justify them, for example:

(opportunity_id, created_at)

Do not add speculative indexes.

29. Migration

Create an Alembic migration for:

content_briefs

Before migration:

Inspect existing models:

content_opportunity

persona

pain_point

desire

audience_question

Inspect existing migrations.

Verify naming conventions.

Verify foreign-key targets.

Verify cascade behavior.

Verify enum patterns.

Verify timestamp conventions.

Verify JSONB metadata conventions.

Do not modify unrelated migrations.

Migration must include a working downgrade.

30. Reuse — Do Not Duplicate

Reuse:

OpportunityScorer
ContentOpportunityRepository
Existing workspace ownership helpers
Existing AI Router
Existing GeminiProvider
Existing AITask enum
Existing enum patterns
Existing metadata JSONB pattern
Existing pagination pattern
Existing timestamp conventions

Do NOT create:

second scoring engine
second AI provider abstraction
second AI router
second workspace authorization helper
separate creator brief model
separate business brief model

Add focused helpers only where genuinely required.

31. Tests

Follow the established test layout.

Recommended:

tests/test_content_briefs.py

CRUD

Test:

create with only opportunity_id using deterministic composition

create with AI enabled and mocked success

create with AI enabled and mocked failure

create fully manual brief

retrieve

list by opportunity

list by profile

update strategic fields

update status through valid lifecycle

reject invalid status transition

delete

Deterministic Composition

Test:

title fallback: market signal

title fallback: audience signal

title fallback: performance insight

title fallback: opportunity title

objective inheritance

format inheritance

CTA strategy per objective

exactly 3 deterministic key points

strategic rationale copied verbatim

default tone when brand voice unavailable

profile brand voice is respected when available

AI Enrichment

Mock AIRouter.

Never call real Gemini.

Test:

successful BriefCompositionLLMResult

schema validation failure

router timeout

provider unavailable

provider not configured

AI output contains malformed fields

prompt version equals:
content_brief_v1

provider/model metadata populated on success

AI failure does not prevent deterministic persistence

failed enrichment results in:
generation_source = deterministic

Ownership / Isolation

Workspace A must not:

retrieve Workspace B brief

update Workspace B brief

delete Workspace B brief

create against Workspace B opportunity

reference Workspace B persona

reference Workspace B pain point

reference Workspace B desire

reference Workspace B audience question

All must return:

404

Cross-Profile

Profile A must not reference Profile B resources.

Return:

404

Creator Support

Verify a creator profile without BusinessContext can create:

deterministic brief
AI-assisted brief

BusinessContext is not required.

Business Support

Verify a business profile with BusinessContext can create:

deterministic brief
AI-assisted brief

Business-specific data remains optional.

Regression

All Day 1–10 tests must continue to pass:

ContentProfile
Brand Intelligence
Audience Intelligence
Market Intelligence
Performance Intelligence

MarketSignal
AudienceSignal

ContentOpportunity
OpportunityScorer

ContentPerformance
PerformanceAnalysis
PerformanceInsight

AIRouter
GeminiProvider

Day 11 is additive.

32. No AI Content Generation

Day 11 does NOT generate:

captions
final hooks
scripts
images
videos
voiceovers
UGC assets
final CTA copy

The AI Router is used only for strategic enrichment.

The following are allowed:

strategic angle
big idea
voice guidance
strategic key points
supporting context derived from supplied intelligence

If the AI begins producing final creative, Day 11 scope has been violated.

33. No Publishing

Day 11 does NOT implement:

social publishing
scheduling
asset upload
Facebook API
Instagram API
TikTok API
YouTube API
LinkedIn API
X API
OAuth
webhooks

Publishing belongs to a later development day.

34. No External Intelligence Collection

Day 11 does NOT implement:

trend scraping
competitor scraping
social listening
search API integration
review/comment ingestion
external intelligence collection

Day 11 consumes existing structured intelligence.

35. Preserve Day 7–10 Behavior

The following must continue working unchanged:

MarketSignal → ContentOpportunity

AudienceSignal → ContentOpportunity

PerformanceInsight → ContentOpportunity

The following remain single implementations:

OpportunityScorer
AIRouter
GeminiProvider
Workspace/profile isolation helpers

Do not fork them for briefs.

36. Architecture After Day 11

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
            ↓
        ContentPerformance
            ↓
        PerformanceAnalysis
            ↓
        PerformanceInsight

MarketSignal ─────────┐
                      │
AudienceSignal ───────┼──▶ ContentOpportunity ──▶ ContentBrief
                      │
PerformanceInsight ───┘

The strategic pipeline now reaches the brief stage.

The brief retains lineage to:

Profile
  ↓
Signal / Insight
  ↓
Opportunity
  ↓
Brief

Future creation must consume the brief rather than bypassing it.

37. Definition of Done

Day 11 is complete when:

ContentBrief model exists

Alembic migration exists with working downgrade

ContentBriefRepository exists

ContentBriefService exists

BriefComposer exists

Pydantic schemas exist

all required API endpoints exist

deterministic composition works without AI

AI-assisted composition works through Day 10 AIRouter

AI failure safely falls back to deterministic composition

brief_version = "v1" is stored

generation_source is server-controlled

generation_source is correct for manual, deterministic, and AI-assisted paths

metadata.ai.prompt_version = "content_brief_v1" is stored on AI success

AI provider/model metadata is stored on AI success

workspace isolation returns 404

profile isolation returns 404

optional intelligence references are ownership-validated

creator profiles work without BusinessContext

business profiles work with BusinessContext

deterministic brief always contains required strategic fields

deterministic key points contain exactly 3 items

no final hooks/captions/scripts are generated

no publishing functionality exists

existing Day 1–10 tests still pass

Day 11 tests pass

uv run ruff check . passes

uv run ruff format --check . passes

uv run pytest passes

Alembic upgrade/downgrade is validated locally

38. Explicit Out-of-Scope

The following are NOT part of Day 11:

ContentItem
Asset
Hook generation
Final hook writing
Caption generation
Script generation
Voiceover / audio generation
Image generation
Video generation
UGC generation
Remix
Publishing
Scheduling
Social API integration
OAuth
Token storage
Webhooks
Background workers
Celery
Kafka
RabbitMQ
Docker
Kubernetes
Microservices
Embeddings
Vector database
RAG
Multi-agent orchestration
AI billing
Usage metering
Speculative infrastructure

Keep Day 11 focused on the:

Content Brief Engine

39. Final Architectural Rule

Day 11 must strengthen the core product loop:

Understand
    ↓
Decide
    ↓
BRIEF
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

The ContentBrief is the strategic contract between Intelligence/Strategy and Creation.

The implementation must remain:

Deterministic-first
        +
AI-enriched-second
        +
Profile-aware
        +
Opportunity-linked
        +
Traceable

The system must never allow Day 11 to become an AI content generator.

The next creation layer should consume the ContentBrief rather than independently deciding what the profile should create.