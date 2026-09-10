# AI CONTENT STUDIO — DAY 13 IMPLEMENTATION SPECIFICATION

## Multi-Variant Creative Generation

---

## 1. DAY 13 OBJECTIVE

Implement the first multi-variant creative capability in AI Content Studio.

Day 12 established:

ContentBrief → ContentDraft

Day 13 extends this to:

ContentBrief
    ↓
ContentDraft
    ↓
ContentDraftVariation
    ├── Hook × N
    └── Caption × N
    ↓
User selects preferred variation
    ↓
ContentDraft is updated

The purpose of Day 13 is to allow users to generate multiple execution alternatives from an existing ContentDraft without changing the underlying strategic decision.

Day 13 is an EXECUTION-LAYER feature.

It must NOT become another strategy engine.

---

# 2. CORE ARCHITECTURAL PRINCIPLE

The strategic hierarchy remains:

ContentProfile
    ↓
ContentOpportunity
    ↓
ContentBrief
    ↓
ContentDraft
    ↓
ContentDraftVariation

The system must preserve this distinction:

ContentBrief
= Strategic contract

ContentDraft
= Primary creative execution

ContentDraftVariation
= Alternative creative execution

A variation may change HOW the idea is expressed.

A variation must NOT change WHY the content exists.

Therefore, variations must remain constrained by the parent ContentBrief.

---

# 3. FORBIDDEN ARCHITECTURE

DO NOT implement:

Trend
    ↓
Generate 10 hooks
    ↓
Generate content

DO NOT allow variations to redefine:

- content objective
- audience
- content pillar
- topic
- strategic angle
- target emotion
- success metrics
- recommended format
- business objective

These belong to the strategic layer.

Day 13 only creates alternative creative expressions.

---

# 4. DAY 13 SCOPE

Implement ONLY:

1. ContentDraftVariation database model
2. Alembic migration
3. Repository
4. Service
5. Pydantic request/response schemas
6. API endpoints
7. Hook variation generation
8. Caption variation generation
9. AI-assisted generation through existing AI infrastructure
10. Deterministic fallback generation
11. Variation selection
12. Synchronization of selected variation into ContentDraft
13. Tests
14. Regression testing for Days 1–12

Do NOT implement:

- image generation
- video generation
- full script generation
- remix engine
- publishing
- scheduling
- social platform APIs
- performance tracking
- analytics
- new AI providers
- new AI architecture
- trend detection
- new strategy logic

---

# 5. CONTENT DRAFT VARIATION MODEL

Create:

ContentDraftVariation

Recommended fields:

- id
- draft_id
- variation_type
- variation_index
- content
- rationale
- generation_source
- ai_provider
- ai_model
- prompt_version
- is_selected
- created_at
- updated_at

---

## 5.1 variation_type

Allowed values ONLY:

- hook
- caption

Do not create separate tables for hooks and captions.

Use one unified variation model.

Future variation types may be added later, but Day 13 must strictly support only these two.

---

# 6. VARIATION INDEX

Each variation must have:

variation_index: integer

Example:

Hook:
- index 1
- index 2
- index 3

Caption:
- index 1
- index 2
- index 3

Enforce uniqueness:

(draft_id, variation_type, variation_index)

This prevents duplicate indexes for the same draft and variation type.

---

# 7. SELECTION RULE

Only ONE variation of each type may be selected for a draft.

Therefore:

A draft may have:

1 selected hook
+
1 selected caption

but never:

2 selected hooks

or:

2 selected captions.

Prefer enforcing this at the PostgreSQL database level using a partial unique index:

UNIQUE (draft_id, variation_type)
WHERE is_selected = true

Application-level validation must also exist.

---

# 8. GENERATION SOURCE

Allowed values:

- deterministic
- ai

The server must determine this value.

The client must NOT be able to claim:

generation_source = "ai"

or:

generation_source = "deterministic"

The service decides this based on actual execution.

---

# 9. AI METADATA

The following fields must be nullable:

- ai_provider
- ai_model
- prompt_version

For deterministic generation:

ai_provider = null
ai_model = null
prompt_version = null

For AI generation:

populate them from the actual AI execution metadata.

Do NOT hardcode fake provider/model information.

---

# 10. GENERATION REQUEST

Endpoint:

POST

/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations

Request:

{
  "variation_type": "hook",
  "count": 3,
  "use_ai": true
}

or:

{
  "variation_type": "caption",
  "count": 3,
  "use_ai": true
}

---

# 11. COUNT RULES

Default:

count = 3

Minimum:

1

Maximum:

5

Therefore:

1 ≤ count ≤ 5

Reject invalid values.

The server must enforce these limits.

---

# 12. AI GENERATION BEHAVIOR

When:

use_ai = true

the service should execute:

ContentDraft
    ↓
Load ContentBrief
    ↓
Build constrained generation request
    ↓
AI Orchestrator
    ↓
AI Router
    ↓
AI Provider
    ↓
Configured model

The service must NOT import Gemini/OpenAI/Claude/etc. directly.

---

# 13. EXISTING AI ARCHITECTURE MUST BE REUSED

Use the architecture already established in Day 10:

Application Service
    ↓
AI Orchestrator
    ↓
AI Router
    ↓
AI Provider
    ↓
Model

Do NOT create:

- another AI client
- another model router
- another provider abstraction
- direct Gemini SDK calls
- direct OpenAI SDK calls
- direct Anthropic SDK calls

Day 13 extends the existing AI infrastructure.

---

# 14. NEW AI TASK TYPES

Add:

HOOK_GENERATION

CAPTION_GENERATION

These must be added to the existing AI task system.

Do NOT create a second task registry.

Do NOT create a separate generation architecture.

---

# 15. HOOK GENERATION

Hook generation must consider:

ContentBrief
+
ContentDraft

Relevant strategic constraints include:

- objective
- target audience
- topic
- content pillar
- strategic angle
- target emotion
- key message
- recommended format
- existing draft context

The generated hook must remain consistent with the strategic brief.

The hook is a creative execution.

It is NOT a new strategic angle.

---

# 16. CAPTION GENERATION

Caption generation must consider:

ContentBrief
+
ContentDraft

The caption should be based on the actual draft content.

Relevant constraints include:

- objective
- target audience
- topic
- strategic angle
- target emotion
- key message
- CTA strategy
- existing draft body/content

The caption must remain consistent with the strategic intent.

---

# 17. IMPORTANT DISTINCTION

Do NOT confuse:

CTA strategy

with:

final CTA copy.

The ContentBrief may contain:

"encourage saving"

The generated caption may contain:

"Save this post so you can come back to it later."

Therefore:

ContentBrief
= strategic CTA direction

ContentDraftVariation
= actual creative wording

---

# 18. AI STRUCTURED OUTPUT

The AI must return a collection.

Use a schema conceptually equivalent to:

class ContentVariationLLMResult(BaseModel):
    variations: list[ContentVariationLLMItem]


class ContentVariationLLMItem(BaseModel):
    content: str
    rationale: str

The AI must NOT generate:

- database IDs
- variation indexes
- profile IDs
- draft IDs
- generation source
- provider metadata

The application assigns these.

---

# 19. AI VALIDATION

The service must validate:

- response structure
- variation count
- content is non-empty
- rationale is non-empty
- no invalid variation type
- no unexpected strategic fields

If AI returns fewer variations than requested:

The service may use deterministic fallback to complete the result.

If AI fails entirely:

Use deterministic fallback.

The endpoint should remain failure-safe.

---

# 20. DETERMINISTIC FALLBACK

Day 13 MUST work without an AI provider.

When:

use_ai = false

generate deterministic variations.

When:

use_ai = true

but AI fails:

fallback to deterministic generation.

At least one valid variation must be produced when fallback generation is possible.

Prefer generating the requested number when practical.

---

# 21. DETERMINISTIC HOOK FALLBACK

Use the existing:

ContentBrief
+
ContentDraft

to create simple but strategically aligned hook templates.

Examples:

"Here's what most people get wrong about {topic}."

"Before you create another {format}, understand this about {topic}."

"If you're trying to {objective}, start with this."

The exact templates should fit the project's existing domain conventions.

Do NOT create random generic hooks disconnected from the brief.

---

# 22. DETERMINISTIC CAPTION FALLBACK

Use:

ContentBrief
+
ContentDraft

to construct a basic caption.

It should preserve:

- topic
- key message
- strategic angle
- CTA strategy

The deterministic fallback does not need to be highly creative.

Its purpose is reliability.

---

# 23. RATIONALE

Every variation must contain:

rationale

This applies to both:

AI-generated variations

AND

deterministic variations.

For AI:

rationale explains the creative reasoning.

For deterministic:

rationale explains which template/constraint was used.

IMPORTANT:

Rationale is NOT strategic evidence.

Do not treat it as evidence for:

- audience intelligence
- market intelligence
- performance intelligence

Strategic evidence belongs to the intelligence/strategy layers.

---

# 24. API ENDPOINTS

## Generate Variations

POST

/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations

Request:

{
  "variation_type": "hook",
  "count": 3,
  "use_ai": true
}

Response:

Return generated variations.

---

## List Variations

GET

/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations

Optional query:

?variation_type=hook

or:

?variation_type=caption

If no type is supplied:

return both.

---

## Select Variation

PATCH

/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations/{variation_id}

Request:

{
  "is_selected": true
}

Only selection behavior is required for Day 13.

---

# 25. SELECTION TRANSACTION

Selection must be atomic.

When selecting a variation:

1. Verify profile ownership
2. Verify draft ownership
3. Verify variation belongs to draft
4. Verify variation type
5. Unselect existing selected variation of the same type
6. Select requested variation
7. Synchronize ContentDraft
8. Commit transaction

Do not perform these as unrelated database operations.

---

# 26. CONTENT DRAFT SYNCHRONIZATION

Selection must update the parent ContentDraft.

For hook:

selected hook
    ↓
ContentDraft.hook

For caption:

selected caption
    ↓
ContentDraft.caption

Do NOT overwrite unrelated fields.

For example:

Selecting a hook must NOT modify:

- body
- title
- CTA
- brief_id
- platform
- format
- profile_id

---

# 27. CAPTION FIELD

If ContentDraft from Day 12 does not already contain:

caption

add:

caption: str | None

Do NOT overload:

body

to store caption content.

Body and caption have different semantic roles.

---

# 28. LINEAGE

Strategic lineage is relational:

ContentDraftVariation
    ↓
ContentDraft
    ↓
ContentBrief
    ↓
ContentOpportunity
    ↓
MarketSignal / AudienceSignal
    ↓
ContentProfile

Do NOT duplicate all of these IDs inside variation metadata.

The relationship should come from the database model.

---

# 29. BRIEF IMMUTABILITY

ContentBrief remains the strategic contract.

Generating variations must NOT modify the ContentBrief.

Selecting a variation must NOT modify the ContentBrief.

Variation generation must not be allowed to:

- change objective
- change audience
- change topic
- change angle
- change pillar
- change success metrics

---

# 30. PROFILE TYPES

Day 13 must work for all supported ContentProfile types.

At minimum test:

Creator:

businessContext = null

and:

Business:

businessContext exists

The variation engine must not assume that every profile has:

- products
- services
- offers
- commercial objectives

Creator workflows must work without BusinessContext.

---

# 31. SERVICE RESPONSIBILITIES

Create a dedicated service, conceptually:

ContentDraftVariationService

Responsibilities:

- validate draft ownership
- load ContentDraft
- load ContentBrief
- validate variation type
- validate count
- construct AI request
- call AI Orchestrator
- process AI response
- perform deterministic fallback
- create variations
- select variation
- synchronize ContentDraft
- preserve transaction boundaries

The service must not contain provider-specific SDK code.

---

# 32. REPOSITORY RESPONSIBILITIES

Repository should handle persistence operations such as:

- create variation
- list variations
- get variation
- find selected variation
- select variation
- update variation

Use the project's established repository patterns.

Do not put business rules inside the repository.

---

# 33. ROUTER RESPONSIBILITIES

Routers must remain thin.

Router:

- parses request
- resolves dependencies
- calls service
- maps response

Router must NOT contain:

- AI logic
- generation templates
- strategy logic
- selection transaction logic
- provider-specific code

---

# 34. PYDANTIC SCHEMAS

Create appropriate schemas for:

Generation request

Variation response

Variation list response if project conventions require it

Selection request

Keep request schemas separate from database models.

Do not expose internal database implementation unnecessarily.

---

# 35. ERROR HANDLING

Handle at least:

- profile not found
- draft not found
- variation not found
- variation does not belong to draft
- draft does not belong to profile
- brief not found
- invalid variation type
- invalid count
- invalid selection request
- AI generation failure
- malformed AI response

Follow existing project error conventions.

Do not introduce a completely new error architecture.

---

# 36. DATABASE CONSTRAINTS

Implement appropriate database constraints.

At minimum:

- foreign key draft_id → content_drafts.id
- valid variation_type
- valid generation_source
- variation_index >= 1
- uniqueness of:
  (draft_id, variation_type, variation_index)

And preferably:

partial unique index:

(draft_id, variation_type)
WHERE is_selected = true

---

# 37. MIGRATION

Create an Alembic migration for:

content_draft_variations

Include:

- table
- indexes
- foreign key
- uniqueness constraints
- selection uniqueness constraint/index

Follow the existing migration conventions.

---

# 38. AI PROMPT DESIGN

The AI prompt must clearly communicate:

You are generating alternative creative executions.

You are NOT redefining strategy.

The ContentBrief is authoritative.

The output must respect:

- objective
- audience
- topic
- strategic angle
- emotion
- key message
- CTA strategy
- format

For caption generation, use the actual ContentDraft content as additional context.

For hook generation, use the draft context without allowing the model to replace the strategy.

---

# 39. AI TASK POLICY

Add policies to the existing AI routing system.

For example:

HOOK_GENERATION
→ configured creative generation model

CAPTION_GENERATION
→ configured creative generation model

Use the project's existing routing abstraction.

Do not hardcode provider SDK logic inside the variation service.

---

# 40. MODEL ROUTING

The system should remain provider-agnostic.

Conceptually:

HOOK_GENERATION
    ↓
AI Router
    ↓
Configured Provider
    ↓
Configured Model

CAPTION_GENERATION
    ↓
AI Router
    ↓
Configured Provider
    ↓
Configured Model

Do not introduce another router.

---

# 41. DETERMINISTIC MODE

When:

use_ai = false

the execution path must be:

Request
    ↓
Variation Service
    ↓
Deterministic Generator
    ↓
ContentDraftVariation

No AI call should occur.

This mode is important for:

- tests
- local development
- predictable behavior
- provider outages
- cost control

---

# 42. AI FALLBACK MODE

When:

use_ai = true

execution should be:

Request
    ↓
Variation Service
    ↓
AI Orchestrator
    ↓
AI Router
    ↓
AI Provider
    ↓
Success?
    ├── YES → save AI variations
    └── NO → deterministic fallback

The system must not crash merely because the AI provider is unavailable.

---

# 43. TESTING REQUIREMENTS

Implement unit and integration tests.

At minimum test:

## Model

- variation creation
- variation indexes
- constraints

## Generation

- hook generation
- caption generation
- count = 1
- count = 3
- count = 5
- count > 5 rejected
- count < 1 rejected

## Deterministic

- use_ai=false
- no provider call
- valid fallback content

## AI

- mocked AI provider
- valid structured response
- malformed response
- provider failure
- fallback execution

## Selection

- select hook
- select caption
- replacing selected hook
- replacing selected caption
- cannot select variation from another draft
- selected variation synchronizes ContentDraft

## Isolation

- profile A cannot access profile B drafts
- profile A cannot access profile B variations

## Business/Creator

Test:

Creator without BusinessContext

Business with BusinessContext

Both must work.

---

# 44. REGRESSION TESTING

All existing tests from Days 1–12 must continue passing.

Day 13 must not break:

- authentication
- workspace isolation
- ContentProfile
- Brand Intelligence
- Audience Intelligence
- Market Intelligence
- Performance Intelligence
- MarketSignal
- AudienceSignal
- ContentOpportunity
- ContentBrief
- ContentDraft
- AI Orchestrator
- AI Router
- AI Provider abstraction

---

# 45. QUALITY REQUIREMENTS

Before considering Day 13 complete, run:

- formatting
- linting
- type checking if configured
- unit tests
- integration tests
- full test suite
- migration validation

Use the project's existing tooling.

Do not introduce a new tooling stack.

---

# 46. ARCHITECTURAL RULES

The implementation MUST continue to follow:

FastAPI
+
SQLAlchemy
+
PostgreSQL
+
Alembic
+
Pydantic

Architecture:

Thin Router
    ↓
Application Service
    ↓
Repository
    ↓
SQLAlchemy

AI:

Application Service
    ↓
AI Orchestrator
    ↓
AI Router
    ↓
AI Provider
    ↓
Model

No:

- LangChain
- LangGraph
- microservices
- direct provider SDK imports in domain services
- generic AI generation endpoint

---

# 47. NO GENERIC AI ENDPOINT

Do NOT create:

POST /api/v1/ai/generate

Day 13 generation must be domain-specific:

POST /api/v1/profiles/{profile_id}/drafts/{draft_id}/variations

The API represents a product capability, not an AI infrastructure capability.

---

# 48. PRODUCT PHILOSOPHY

Remember:

AI Content Studio is not primarily an AI content generator.

The product's competitive advantage is:

Intelligence
    ↓
Strategy
    ↓
Opportunity
    ↓
Brief
    ↓
Creation
    ↓
Measurement
    ↓
Learning

Day 13 operates only here:

Brief
    ↓
Creation
    ↓
Variation

Therefore Day 13 must NOT introduce a new strategic decision layer.

---

# 49. DEFINITION OF DONE

Day 13 is complete only when:

[ ] ContentDraftVariation model exists

[ ] Alembic migration exists

[ ] variation_type supports hook/caption

[ ] variation_index exists

[ ] variation index uniqueness enforced

[ ] selected variation uniqueness enforced

[ ] rationale exists

[ ] generation_source exists

[ ] AI metadata fields exist

[ ] updated_at exists

[ ] repository exists

[ ] service exists

[ ] Pydantic schemas exist

[ ] generation endpoint exists

[ ] list endpoint exists

[ ] selection endpoint exists

[ ] HOOK_GENERATION task exists

[ ] CAPTION_GENERATION task exists

[ ] existing AI Orchestrator is reused

[ ] existing AI Router is reused

[ ] no direct provider SDK usage in domain/service layer

[ ] AI structured output is validated

[ ] deterministic fallback exists

[ ] use_ai=false works without AI

[ ] AI failure falls back safely

[ ] hook selection updates ContentDraft.hook

[ ] caption selection updates ContentDraft.caption

[ ] selection is transactional

[ ] ContentBrief remains unchanged

[ ] strategic lineage is preserved

[ ] creator without BusinessContext works

[ ] business with BusinessContext works

[ ] profile isolation is enforced

[ ] Day 1–12 regression tests pass

[ ] formatting passes

[ ] linting passes

[ ] type checking passes if configured

[ ] full test suite passes

[ ] no unrelated features are implemented

---

# 50. FINAL DAY 13 ARCHITECTURE

The final architecture should be:

                    CONTENT PROFILE
                          │
                          ▼
                  CONTENT OPPORTUNITY
                          │
                          ▼
                    CONTENT BRIEF
                  (Strategy Contract)
                          │
                          ▼
                    CONTENT DRAFT
                 (Primary Execution)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       HOOK VARIATIONS         CAPTION VARIATIONS
            × N                       × N
              │                       │
              └───────────┬───────────┘
                          ▼
                    USER SELECTION
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        ContentDraft.hook     ContentDraft.caption
                          │
                          ▼
                    FUTURE PUBLISH
                          │
                          ▼
                PERFORMANCE INTELLIGENCE
                          │
                          ▼
                       LEARNING
                          │
                          ▼
                  CONTENT INTELLIGENCE


==================================================
END OF DAY 13 SPECIFICATION
==================================================