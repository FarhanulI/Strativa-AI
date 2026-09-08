Day 12 — Content Creation Engine v1

1. Objective

Build the first Content Creation Engine that converts a ContentBrief into an executable ContentDraft.

Day 12 begins the execution layer after the Strategy → Opportunity → Brief pipeline.

ContentProfile
      ↓
ContentOpportunity
      ↓
ContentBrief
      ↓
Content Creation Engine
      ↓
ContentDraft

The core rule remains:

Creation executes strategy; it does not replace strategy.

The Creation Engine must consume the ContentBrief rather than independently deciding what content should be created.

2. Scope

Implement

Day 12 implements:

ContentDraft domain model

Content creation schemas

Content draft repository

ContentCreationService

Deterministic content creation

AI-assisted content creation

CONTENT_CREATION AI task

Existing AI Router integration

Gemini integration through the existing AI abstraction

AI failure → deterministic fallback

Strategic lineage

Draft lifecycle

CRUD APIs

Isolation validation

Unit/integration tests

Alembic migration

Do NOT implement

Do not implement:

publishing

scheduling

Facebook/Instagram APIs

TikTok/YouTube APIs

image generation

video generation

UGC generation

voice generation

remix engine

asset assembly

performance analytics

performance learning

autonomous agents

queues/workers

RAG

vector databases

microservices

LangChain

LangGraph

These belong to later milestones.

3. Architectural Position

Day 12 must preserve:

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

Day 12 implements only:

Brief
  ↓
Create

The full product flow becomes:

ContentProfile
      ↓
Content Intelligence
      ↓
ContentOpportunity
      ↓
ContentBrief
      ↓
ContentDraft

4. ContentDraft Model

Create a first-class ContentDraft model.

Recommended fields:

ContentDraft
├── id
├── profile_id
├── brief_id
├── platform
├── format
├── title
├── hook
├── body
├── cta
├── status
├── generation_source
├── composition_mode
├── ai_provider
├── ai_model
├── prompt_version
├── metadata
├── created_at
└── updated_at

Field semantics

profile_id

Owner ContentProfile.

brief_id

The ContentBrief that produced this draft.

This establishes:

ContentDraft
    ↓
ContentBrief
    ↓
ContentOpportunity
    ↓
Signal

platform

The target platform inherited from the ContentBrief.

Examples:

facebook
instagram
tiktok
youtube
linkedin
x

Do not create separate platform-specific creation engines.

format

The target format inherited from the ContentBrief.

Examples:

text_post
reel
short_video
carousel
image
story
ugc
blitz
remix

Day 12 primarily produces textual draft output.

For visual/video formats, the textual output can be the executable script/content direction. Actual media generation comes later.

title

Optional title/headline.

hook

Executable hook text.

Day 11 defines strategic hook direction. Day 12 may turn that direction into actual hook wording.

body

Main content.

For video-oriented formats this can contain the draft script.

cta

Executable CTA copy.

Day 11:

cta_strategy = "encourage saving"

Day 12:

cta = "Save this post before your next match."

status

Recommended lifecycle:

draft
ready
approved
archived

Default:

draft

generation_source

Server-controlled:

deterministic
ai
ai_fallback
manual

The client must not be able to claim the generation source.

composition_mode

Use:

compose
manual

Default:

compose

ai_provider

Nullable.

Example:

gemini

Only populate when AI generation actually occurs.

ai_model

Nullable.

prompt_version

Nullable.

Example:

content_creation_v1

metadata

Store lineage and generation context that is not already a first-class column.

Example:

{
  "lineage": {
    "profile_id": "...",
    "brief_id": "...",
    "opportunity_id": "...",
    "source_signal_type": "audience_question",
    "source_signal_id": "..."
  },
  "creation": {
    "platform": "instagram",
    "format": "reel"
  },
  "ai": {
    "provider": "gemini",
    "model": "...",
    "prompt_version": "content_creation_v1"
  }
}

Do not duplicate first-class fields inside metadata.

5. Relationships

Required:

ContentProfile
      ↓
ContentBrief
      ↓
ContentDraft

A draft must belong to the same profile as its brief.

Reject:

Profile A
   ↓
Brief belonging to Profile B
   ↓
Draft

Expected response:

404

Follow the existing workspace/profile isolation conventions from previous days.

6. Creation Request

Use an explicit composition mode.

Recommended:

class ContentDraftCreate(BaseModel):
    composition_mode: Literal["compose", "manual"] = "compose"
    use_ai: bool = False
    title: str | None = None
    hook: str | None = None
    body: str | None = None
    cta: str | None = None

The server controls inherited and generated fields.

7. Composition Rules

compose + use_ai=false

Use:

DeterministicContentCreator

Result:

generation_source = deterministic

compose + use_ai=true

Use:

ContentCreationService
      ↓
AI Orchestrator
      ↓
AI Router
      ↓
AI Provider

Successful AI generation:

generation_source = ai

If AI fails:

AI failure
      ↓
DeterministicContentCreator
      ↓
generation_source = ai_fallback

manual

Use client-provided content.

Result:

generation_source = manual

Manual content must still remain linked to the ContentBrief.

8. Brief Validation

A ContentDraft should only be created from an executable brief.

Recommended allowed statuses:

ready
approved

Reject:

draft
archived

This prevents bypassing the strategic contract.

Flow:

POST draft
    ↓
Load brief
    ↓
Validate ownership
    ↓
Validate brief status
    ↓
Create draft

9. AI Task

Add:

CONTENT_CREATION

to the existing AI task system.

Required capabilities:

TEXT_GENERATION
STRUCTURED_OUTPUT
REASONING

Initial provider policy:

CONTENT_CREATION
      ↓
Gemini

The task policy must be defined in the AI routing layer.

Do not hardcode Gemini inside ContentCreationService.

10. AI Architecture

Use the Day 10 architecture:

ContentCreationService
        ↓
ContentCreator
        ↓
AI Orchestrator
        ↓
AI Router
        ↓
Task Policy
        ↓
AI Provider
        ↓
Gemini

No direct SDK imports from domain/application services.

The provider remains replaceable.

Future providers can include:

OpenAI
Anthropic
Perplexity
other providers

without changing the Creation Engine contract.

11. AI Response Schema

Create:

class ContentCreationLLMResult(BaseModel):
    title: str | None
    hook: str
    body: str
    cta: str | None

The model must not control:

profile_id
brief_id
platform
format
status
generation_source
composition_mode
provider
model
prompt_version

These are application-owned.

12. Prompt

Use a versioned prompt:

content_creation_v1

The system prompt should instruct the model to:

execute the supplied ContentBrief

preserve the strategic objective

preserve the target audience

preserve the topic

preserve the recommended format

preserve the strategic angle

use the supplied story structure

turn hook direction into executable wording

turn CTA strategy into executable CTA copy

respect platform context

respect target emotion

use supplied visual/audio direction when relevant

avoid unsupported factual claims

avoid inventing statistics

avoid inventing audience research

avoid changing strategic intent

The model should create content, not redesign the strategy.

13. AI Context

The AI prompt should receive relevant structured brief context.

Example:

Platform:
Instagram

Format:
Reel

Objective:
growth

Audience:
Beginner football fans

Content pillar:
Football tactics

Topic:
Why high pressing fails

Strategic angle:
Explain the coordination problem behind failed pressing.

Hook direction:
Challenge the belief that pressing simply means running toward the ball.

Target emotion:
curiosity

Story structure:
Hook → Problem → Explanation → Example → Takeaway

Key message:
Effective pressing depends on coordinated triggers and team shape.

CTA strategy:
encourage comments

Visual direction:
Simple tactical diagrams and match examples.

Duration:
45 seconds

The AI should transform this strategic input into executable content.

14. Deterministic Creator

Day 12 must work without AI.

Create a deterministic creator that produces a minimal usable draft from the ContentBrief.

Example:

Hook:
"Your team doesn't have a pressing problem.
It has a coordination problem."

Body:
Derived from the brief's strategic angle,
story structure and key message.

CTA:
Derived from CTA strategy.

The deterministic creator does not need sophisticated language generation.

Its purpose is:

local development

predictable behavior

testability

provider independence

AI fallback

15. Deterministic Generation Rules

The deterministic creator should use:

strategic_angle
+
key_message
+
story_structure
+
cta_strategy

and optionally:

topic
target_emotion
visual_direction
audio_direction

Do not invent external facts.

If a required field is unavailable, use a safe generic composition rather than fabricating information.

16. AI Failure Handling

Required:

use_ai=true
      ↓
AI Router
      ↓
provider
      ↓
success
   → AI draft

failure
   ↓
deterministic fallback
   ↓
AI fallback draft

The API must not expose:

API keys

provider credentials

stack traces

raw SDK exceptions

internal prompt details

Internally log sufficient diagnostics for debugging.

17. Generation Metadata

When deterministic:

{
  "creation": {
    "method": "deterministic"
  }
}

When AI:

{
  "ai": {
    "provider": "gemini",
    "model": "...",
    "prompt_version": "content_creation_v1"
  }
}

When AI fallback occurs:

{
  "ai": {
    "provider": "gemini",
    "model": "...",
    "prompt_version": "content_creation_v1",
    "fallback": true
  }
}

Do not expose secrets.

18. Strategic Lineage

Every draft must preserve the complete strategic chain:

ContentDraft
    ↓
ContentBrief
    ↓
ContentOpportunity
    ↓
MarketSignal / AudienceSignal / PerformanceInsight

Store enough lineage in metadata to answer:

Why was this content created?

Example:

{
  "lineage": {
    "brief_id": "...",
    "opportunity_id": "...",
    "source_signal_type": "audience_question",
    "source_signal_id": "..."
  }
}

Do not copy entire intelligence objects into the draft.

The goal is traceability, not duplication.

19. API

Implement:

POST   /api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts

GET    /api/v1/profiles/{profile_id}/drafts

GET    /api/v1/profiles/{profile_id}/drafts/{draft_id}

PATCH  /api/v1/profiles/{profile_id}/drafts/{draft_id}

DELETE /api/v1/profiles/{profile_id}/drafts/{draft_id}

Do not create:

POST /api/v1/ai/generate

The API must remain domain-oriented.

20. POST Draft Flow

POST /profiles/{profile_id}/briefs/{brief_id}/drafts
        ↓
Validate profile
        ↓
Validate brief
        ↓
Validate profile ↔ brief
        ↓
Validate brief status
        ↓
Load strategic context
        ↓
Determine composition mode
        ↓
Create draft
        ↓
Persist
        ↓
Return ContentDraft

21. Manual Creation

For:

composition_mode = manual

the client can provide:

{
  "composition_mode": "manual",
  "use_ai": false,
  "title": "Why pressing fails",
  "hook": "Your team doesn't have a pressing problem.",
  "body": "The real issue is coordination...",
  "cta": "What pressing mistake do you see most often?"
}

Server controls:

profile_id
brief_id
platform
format
generation_source
status
timestamps

Manual content still has:

ContentDraft → ContentBrief → ContentOpportunity

lineage.

22. Platform and Format

Do not create:

InstagramCreator
FacebookCreator
TikTokCreator
LinkedInCreator

Use one universal Creation Engine:

ContentBrief
      ↓
ContentCreationEngine
      ↓
platform + format context

Examples:

Instagram + Reel
    → short-form script

Facebook + Text Post
    → post copy

LinkedIn + Text Post
    → professional post

TikTok + Short Video
    → short-form script

The engine remains universal for creators and businesses.

23. Database

Create an Alembic migration for:

content_drafts

Recommended indexes:

profile_id
brief_id
status
platform
format
created_at

Foreign keys:

content_profiles.id
content_briefs.id

Recommended cascade:

ContentProfile
    ↓
ContentBrief
    ↓
ContentDraft

Follow the existing repository's foreign-key conventions.

24. Repository

Create a repository following the existing project pattern.

Responsibilities:

create draft

get draft by ID

list drafts

update draft

delete draft

filter by profile

filter by status/platform/format where appropriate

All queries must remain profile-scoped.

Do not expose drafts from another profile.

25. Service Responsibilities

ContentCreationService

Owns:

profile/brief validation

brief lifecycle validation

strategic context loading

composition selection

AI/fallback behavior

lineage

persistence

ContentCreator

Owns:

translating ContentBrief into AI creation input

calling the AI orchestration layer

validating typed AI output

DeterministicContentCreator

Owns:

predictable non-AI creation

fallback creation

AI Layer

Owns:

provider selection

model selection

structured generation

provider abstraction

AI metadata

26. Suggested Project Structure

Adapt to the existing repository instead of reorganizing unrelated code.

Possible structure:

app/
├── models/
│   └── content_draft.py
│
├── schemas/
│   └── content_draft.py
│
├── repositories/
│   └── content_draft.py
│
├── services/
│   └── content_creation/
│       ├── __init__.py
│       ├── service.py
│       ├── creator.py
│       ├── deterministic.py
│       ├── prompts.py
│       └── schemas.py
│
├── services/ai/
│   ├── ...
│   └── tasks/
│       └── types.py
│
└── api/
    └── ...

Use existing naming and module conventions where they differ.

27. Tests

Model tests

Test:

draft creation

required fields

nullable fields

valid statuses

invalid statuses

valid generation sources

invalid generation sources

valid composition modes

invalid composition modes

Isolation tests

Test:

draft belongs to profile

brief belongs to profile

cross-profile brief rejected

cross-workspace access rejected

draft cannot be accessed through another profile

Brief lifecycle

Test:

ready → allowed
approved → allowed
draft → rejected
archived → rejected

Deterministic creation

Test:

use_ai=false succeeds

output is derived from the brief

generation source is deterministic

no AI provider is required

AI creation

Test:

use_ai=true invokes the AI layer

CONTENT_CREATION task is routed correctly

structured response is accepted

provider/model metadata is stored

generation source is ai

Fallback

Test:

AI provider failure triggers deterministic fallback

generation source is ai_fallback

draft is still usable

raw provider error is not exposed

Manual

Test:

manual draft creation

generation source is manual

manual fields are preserved

lineage is preserved

CRUD

Test:

create

list

retrieve

update

delete

Regression

Run all existing tests from Days 1–11.

28. Acceptance Criteria

Architecture

ContentDraft is a first-class domain model.

Draft belongs to a ContentProfile.

Draft belongs to a ContentBrief.

Creation uses the existing AI abstraction.

Domain/application services do not import Gemini SDK directly.

No generic AI generation endpoint exists.

No LangChain/LangGraph is introduced.

Creation

A ready brief can create a draft.

An approved brief can create a draft.

Deterministic creation works without AI.

AI creation works through the AI Router.

AI failure falls back deterministically.

Manual creation works.

Strategy Integrity

Draft remains linked to its brief.

Brief remains linked to its opportunity.

Strategic lineage is preserved.

Creation does not modify opportunity strategy.

Creation does not independently query trends to decide what to create.

API

POST works.

GET list works.

GET detail works.

PATCH works.

DELETE works.

Cross-profile access returns 404.

Quality

New tests pass.

Existing tests pass.

Ruff passes.

Formatting passes.

Alembic migration is valid.

29. Validation Commands

Run:

uv run pytest
uv run ruff check .
uv run ruff format --check .

Validate Alembic according to the existing project migration workflow.

Do not introduce unrelated refactoring.

30. Implementation Report

After implementation, report:

Day 12 Implementation Report

1. Files created
2. Files modified
3. Database changes
4. Migration
5. Models
6. Schemas
7. Repository
8. Service
9. AI task
10. AI routing
11. Deterministic creator
12. AI fallback
13. API endpoints
14. Strategic lineage
15. Tests
16. Test results
17. Ruff results
18. Formatting results
19. Migration results
20. Assumptions
21. Known technical debt
22. Explicitly deferred scope

31. Example End-to-End Flow

Profile

Type:
creator

Positioning:
Football analyst who explains tactics simply.

Audience:
Beginner and intermediate football fans.

Goal:
growth

Opportunity

Title:
Why high pressing keeps failing for amateur teams

Source:
audience_question

Objective:
growth

Recommended format:
reel

Brief

Strategic angle:
Explain the coordination problem behind failed pressing.

Hook direction:
Challenge the belief that pressing simply means running toward the ball.

Target emotion:
curiosity

Story structure:
Hook → Problem → Explanation → Example → Takeaway

Key message:
Effective pressing depends on coordinated triggers and team shape.

CTA strategy:
encourage comments

ContentDraft

Hook:
"Your team doesn't have a pressing problem.
It has a coordination problem."

Body:
"Most amateur teams press by reacting to the ball.
The best pressing teams react to triggers.

When one player jumps, the next player must know
which passing lane to close and when the defensive line
should move.

If those movements aren't connected, pressing creates
gaps instead of pressure.

The key isn't running more.
It's moving together."

CTA:
"What pressing mistake do you see most often?"

The architectural chain is:

Audience Question
       ↓
Opportunity
       ↓
Brief
       ↓
Draft

Never:

Trend
   ↓
AI
   ↓
Random Draft

32. Future Evolution

Day 12 establishes the general creation layer.

Later creation capabilities can be added without changing the strategic architecture:

ContentBrief
      ↓
ContentCreationEngine
      ├── Hook Generation
      ├── Caption Generation
      ├── Script Generation
      ├── CTA Optimization
      │
      ├── Image Generation
      ├── Video Generation
      ├── UGC Generation
      ├── Voice Generation
      │
      └── Remix / Transformation
              ↓
         Asset Assembly
              ↓
           Publish
              ↓
          Measure
              ↓
            Learn

The strategy contract remains:

ContentProfile
      ↓
ContentOpportunity
      ↓
ContentBrief
      ↓
ContentDraft
      ↓
Published Content
      ↓
Performance Intelligence
      ↓
Learning

33. Core Day 12 Principle

The Content Creation Engine turns a strategic ContentBrief into executable content without bypassing the Strategy Engine.

Day 12 therefore moves AI Content Studio from:

"Here is what you should create."

to:

"Here is the actual content draft created from that strategic decision."

That is the purpose of the Day 12 milestone.