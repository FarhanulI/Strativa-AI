# AI CONTENT STUDIO — DAY 14 IMPLEMENTATION SPECIFICATION

## Content Quality & Strategic Alignment Evaluation

---

# 1. DAY 14 OBJECTIVE
Implement the first Content Evaluation capability in AI Content Studio.

Day 12 established:

ContentBrief → ContentDraft

Day 13 established:

ContentDraft → ContentDraftVariation

Day 14 adds:

ContentDraft / selected Variation
↓
Content Evaluation
↓
Quality + Strategic Alignment Analysis
↓
Score + Findings + Recommendations

The purpose of Day 14 is to determine whether a generated content draft is:

- strategically aligned
- audience aligned
- clear
- compelling
- format appropriate
- consistent with the ContentBrief
- ready for the next execution stage
Day 14 evaluates content.

It does NOT rewrite or regenerate content.

---

# 2. CORE PRODUCT PRINCIPLE
AI Content Studio is not primarily an AI content generator.

Its core value is:

Understand
↓
Decide
↓
Brief
↓
Create
↓
Measure
↓
Learn

Day 14 strengthens the boundary between:

Strategy
and
Creation.

The system should be able to answer:

> "Did the content we created actually execute the strategy correctly?"

---

# 3. STRATEGIC HIERARCHY
The hierarchy remains:

ContentProfile
↓
ContentOpportunity
↓
ContentBrief
↓
ContentDraft
↓
ContentDraftVariation
↓
ContentEvaluation

Evaluation must never become a replacement for:

ContentOpportunity
or
ContentBrief.

---

# 4. EVALUATION INPUT
The evaluator must consider:

## Required
ContentBrief

ContentDraft

## Optional
Selected ContentDraftVariation

The evaluator must NOT independently research trends or invent a new strategy.

---

# 5. WHAT DAY 14 EVALUATES
Evaluate the creative execution against the strategic contract.

At minimum evaluate:

1. Strategic alignment
2. Audience relevance
3. Hook strength
4. Message clarity
5. Narrative coherence
6. Format alignment
7. Emotional alignment
8. CTA alignment
9. Brand/voice alignment
10. Overall quality

---

# 6. EVALUATION DIMENSIONS
Create a typed evaluation result.

Recommended dimensions:

### strategic_alignment
Does the content execute the ContentBrief's strategic angle and objective?

### audience_relevance
Does the content speak to the intended audience?

### hook_strength
Does the opening create enough curiosity/relevance to continue?

### message_clarity
Is the key message understandable?

### narrative_coherence
Does the content logically communicate its idea?

### format_alignment
Does the content fit the recommended format?

### emotional_alignment
Does the content create the intended emotion?

### cta_alignment
Does the CTA follow the brief's CTA strategy?

### brand_alignment
Does the content remain consistent with the profile's positioning and voice?

### overall_quality
Overall creative quality based on the above dimensions.

---

# 7. SCORE MODEL
Each dimension uses:

0.0 → 1.0

Example:

strategic_alignment = 0.92

audience_relevance = 0.84

hook_strength = 0.78

etc.

Overall score should be deterministic from the dimension scores.

Recommended weighted model:

strategic_alignment × 0.20
audience_relevance × 0.15
hook_strength × 0.15
message_clarity × 0.10
narrative_coherence × 0.10
format_alignment × 0.10
emotional_alignment × 0.05
cta_alignment × 0.05
brand_alignment × 0.10

Total:

1.00

Do not allow the AI to arbitrarily invent the overall score.

The application should calculate it.

---

# 8. SCORE CLASSIFICATION
Classify overall score:

> = 0.85
> excellent

> = 0.70
> strong

> = 0.55
> acceptable

> = 0.40
> weak
< 0.40
poor

The classification is deterministic.

---

# 9. FINDINGS
The evaluator should return findings explaining WHY the content received its scores.

A finding should contain:

- dimension
- severity
- summary
- explanation
- recommendation
Severity:

- positive
- warning
- critical
Example:

dimension:
hook_strength

severity:
warning

summary:
Hook is relevant but not sufficiently specific.

explanation:
The opening identifies the topic but does not create a strong reason for the target audience to continue.

recommendation:
Introduce a specific tension, mistake, or unexpected claim.

---

# 10. RECOMMENDATIONS
Recommendations must improve execution.

They must NOT redefine strategy.

Good:

"Make the opening more specific."

"Bring the key insight earlier."

"Use a stronger contrast in the first sentence."

Bad:

"Change the target audience."

"Change the content objective."

"Use a completely different topic."

"Create a sales post instead."

The latter are strategic decisions and are outside Day 14.

---

# 11. EVALUATION MODEL
Create:

ContentEvaluation

Recommended fields:

- id
- profile_id
- draft_id
- variation_id nullable
- overall_score
- classification
- strategic_alignment_score
- audience_relevance_score
- hook_strength_score
- message_clarity_score
- narrative_coherence_score
- format_alignment_score
- emotional_alignment_score
- cta_alignment_score
- brand_alignment_score
- generation_source
- ai_provider nullable
- ai_model nullable
- prompt_version nullable
- metadata
- created_at
- updated_at
variation_id is nullable because the base ContentDraft itself can be evaluated.

---

# 12. EVALUATION FINDINGS MODEL
Create:

ContentEvaluationFinding

Recommended fields:

- id
- evaluation_id
- dimension
- severity
- summary
- explanation
- recommendation
- created_at
Allowed dimensions:

- strategic_alignment
- audience_relevance
- hook_strength
- message_clarity
- narrative_coherence
- format_alignment
- emotional_alignment
- cta_alignment
- brand_alignment
Allowed severity:

- positive
- warning
- critical

---

# 13. WHY USE TWO MODELS
Do not store all findings inside an unstructured JSON blob.

Use:

ContentEvaluation
↓
ContentEvaluationFinding × N

This allows future features such as:

- filtering weak hooks
- showing repeated weaknesses
- comparing variations
- learning from evaluation patterns
- analytics
- future performance correlation
Metadata may still be used for non-core extensibility.

---

# 14. GENERATION SOURCE
Allowed:

- deterministic
- ai
- ai_fallback
The server owns this value.

Client input must not control generation_source.

---

# 15. AI EVALUATION
Use the existing AI architecture:

ContentEvaluationService
↓
AI Orchestrator
↓
AI Router
↓
AI Provider
↓
Configured model

Do NOT directly import:

- Gemini SDK
- OpenAI SDK
- Anthropic SDK
- Perplexity SDK
inside the domain/service implementation.

---

# 16. NEW AI TASK
Add:

CONTENT_EVALUATION

to the existing AI task registry.

Do not create a second AI task system.

---

# 17. AI STRUCTURED OUTPUT
The AI should return only the evaluation dimensions and findings.

Conceptually:

class ContentEvaluationLLMResult(BaseModel):
strategic_alignment: ScoreResult
audience_relevance: ScoreResult
hook_strength: ScoreResult
message_clarity: ScoreResult
narrative_coherence: ScoreResult
format_alignment: ScoreResult
emotional_alignment: ScoreResult
cta_alignment: ScoreResult
brand_alignment: ScoreResult
findings: list[EvaluationFindingResult]

class ScoreResult(BaseModel):
score: float
explanation: str

class EvaluationFindingResult(BaseModel):
dimension: EvaluationDimension
severity: EvaluationSeverity
summary: str
explanation: str
recommendation: str

The AI must NOT return:

- database IDs
- profile IDs
- draft IDs
- variation IDs
- generation_source
- overall_score
- classification
The application assigns/calculates those.

---

# 18. AI SCORE VALIDATION
Every score must satisfy:

0.0 <= score <= 1.0

Reject or normalize invalid AI responses according to existing project conventions.

Missing dimensions must not silently become arbitrary values.

Malformed AI output must trigger fallback behavior.

---

# 19. OVERALL SCORE
Never trust an AI-generated overall score.

Calculate:

overall_score =
strategic_alignment * 0.20

- audience_relevance * 0.15
- hook_strength * 0.15
- message_clarity * 0.10
- narrative_coherence * 0.10
- format_alignment * 0.10
- emotional_alignment * 0.05
- cta_alignment * 0.05
- brand_alignment * 0.10
Round according to project conventions.

---

# 20. CLASSIFICATION
Calculate classification from the application:

> = 0.85 → excellent
> = 0.70 → strong
> = 0.55 → acceptable
> = 0.40 → weak
> < 0.40 → poor
Do not ask the model to determine this.

---

# 21. DETERMINISTIC EVALUATION
Day 14 must support:

use_ai = false

The deterministic evaluator should perform basic structural checks.

Examples:

Strategic alignment:

- required brief fields present
- draft exists
- draft corresponds to brief
Message clarity:

- content is non-empty
- minimum reasonable content length
Hook:

- hook exists
- hook is non-empty
CTA:

- CTA exists where appropriate
- CTA is consistent with brief CTA strategy where detectable
Format:

- draft format matches brief recommended format
Do not pretend deterministic heuristics provide human-level semantic evaluation.

The deterministic evaluator should be conservative.

---

# 22. AI FALLBACK
When:

use_ai = true

and AI fails:

AI Evaluation
↓
Failure
↓
Deterministic Evaluation
↓
ContentEvaluation
generation_source = ai_fallback

The endpoint must remain failure-safe.

---

# 23. VARIATION EVALUATION
If:

variation_id is supplied

evaluate the selected variation as part of the draft execution.

For example:

ContentDraft
hook = original hook

Variation
type = hook
content = alternative hook

The evaluator should use the variation content in the appropriate evaluation context.

Do not modify the variation automatically.

---

# 24. VARIATION COMPARISON
Day 14 may support evaluating multiple variations individually.

Do NOT implement an automatic "winner selection" algorithm yet.

The system may expose scores for:

Hook A
Hook B
Hook C

but the user remains responsible for selection.

Future versions may introduce:

Variation Ranking

or:

Creative Optimization

based on actual performance.

That is out of scope for Day 14.

---

# 25. EVALUATION IMMUTABILITY
An evaluation represents an assessment at a point in time.

Do not silently mutate historical evaluations when the draft changes.

If the draft is changed and evaluated again:

create a new ContentEvaluation.

This creates a historical evaluation trail.

---

# 26. LINEAGE
Preserve:

ContentEvaluation
↓
ContentDraft
↓
ContentBrief
↓
ContentOpportunity
↓
Signal
↓
ContentProfile

If variation is involved:

ContentEvaluation
↓
ContentDraftVariation
↓
ContentDraft
↓
ContentBrief
↓
ContentOpportunity
↓
Signal

Do not duplicate the entire lineage in metadata.

---

# 27. API
Implement:

## Evaluate Draft
POST

/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations

Request:

{
"use_ai": true
}

Optional:

{
"use_ai": true,
"variation_id": "..."
}

The variation must belong to the supplied draft.

---

# 28. LIST EVALUATIONS
GET

/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations

Return historical evaluations.

Newest first according to existing project conventions.

---

# 29. GET EVALUATION
GET

/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations/{evaluation_id}

Return:

- scores
- overall score
- classification
- findings
- generation metadata
- timestamps

---

# 30. NO DELETE REQUIRED
Do not add DELETE unless the existing project's artifact conventions require it.

Historical evaluations are useful for future learning.

---

# 31. SERVICE
Create:

ContentEvaluationService

Responsibilities:

- verify profile ownership
- load draft
- load brief
- optionally load variation
- validate variation ownership
- construct evaluation context
- invoke AI Orchestrator when requested
- validate AI response
- execute deterministic fallback
- calculate overall score
- calculate classification
- persist evaluation
- persist findings
The service owns evaluation orchestration.

---

# 32. REPOSITORY
Create:

ContentEvaluationRepository

Responsibilities:

- create evaluation
- create findings
- get evaluation
- list evaluations
- enforce profile/draft isolation through query filters
Do not place scoring rules inside repository methods.

---

# 33. ROUTER
Router responsibilities:

- parse request
- validate request schema
- resolve dependencies
- call service
- serialize response
No evaluation logic inside routers.

---

# 34. SCHEMAS
Create appropriate Pydantic schemas for:

- evaluation request
- evaluation response
- evaluation finding response
- evaluation list response
Do not expose SQLAlchemy models directly.

---

# 35. DATABASE RELATIONSHIPS
ContentEvaluation:

draft_id → ContentDraft

profile_id → ContentProfile

variation_id → ContentDraftVariation nullable

ContentEvaluationFinding:

evaluation_id → ContentEvaluation

Use foreign keys and indexes following existing conventions.

---

# 36. PROFILE ISOLATION
The API must enforce:

Profile A
↓
Draft A
↓
Evaluation A

Profile A must never access:

Draft B
Evaluation B
Variation B

Cross-profile references must return the project's established not-found/authorization behavior.

---

# 37. CREATOR AND BUSINESS SUPPORT
Test both:

Creator:

businessContext = null

Business:

businessContext exists

Evaluation must work without assuming:

- product
- service
- offer
- commercial objective
For a creator:

CTA alignment should use the existing brief CTA strategy.

For a business:

CTA alignment may additionally consider commercial context if that information already exists in the ContentBrief.

Do not introduce new BusinessContext logic in Day 14.

---

# 38. AI PROMPT RULES
The evaluation prompt must clearly state:

The ContentBrief is authoritative.

Evaluate the ContentDraft against the brief.

Do not invent market information.

Do not invent audience research.

Do not redefine strategy.

Do not recommend changing the objective unless explicitly identifying a severe execution mismatch.

Focus recommendations on improving the creative execution.

The model must use only the supplied:

- ContentBrief
- ContentDraft
- ContentDraftVariation
- relevant profile brand/voice information

---

# 39. IMPORTANT AI BOUNDARY
Do not send unnecessary entire database objects to the model.

Construct a focused evaluation context.

For example:

STRATEGIC CONTEXT

- objective
- audience
- topic
- pillar
- strategic angle
- target emotion
- key message
- format
- CTA strategy
CREATIVE CONTEXT

- title
- hook
- body
- caption
- CTA
- selected variation
BRAND CONTEXT

- positioning
- voice
- tone
Only provide information required for evaluation.

---

# 40. NO EXTERNAL RESEARCH
Day 14 must NOT perform:

- trend research
- competitor research
- web research
- audience research
- market research
The evaluator judges execution against existing strategic context.

Research belongs to Intelligence.

---

# 41. NO AUTOMATIC REWRITING
Do not automatically:

- rewrite hook
- rewrite caption
- rewrite body
- change CTA
- generate new content
Day 14 produces:

Evaluation
+
Findings
+
Recommendations

Future creation/revision functionality may consume those recommendations.

---

# 42. FUTURE EXTENSION
Day 14 should make it possible for a future feature to implement:

Evaluation
↓
Recommendation
↓
Revision
↓
New ContentDraftVersion

But DO NOT implement revision/versioning in Day 14.

---

# 43. TESTING
Implement tests for:

## Model

- evaluation creation
- finding creation
- score constraints
- relationships

## Scoring

- weighted overall score
- classification boundaries
- invalid score handling

## Deterministic

- use_ai=false
- deterministic evaluator
- no AI provider call

## AI

- mocked AI response
- valid structured output
- malformed response
- provider failure
- ai_fallback

## Variation

- evaluate draft without variation
- evaluate draft with variation
- reject variation from another draft

## Isolation

- profile A cannot access profile B evaluation
- profile A cannot evaluate profile B draft

## History

- evaluating the same draft twice creates separate evaluations

## Creator

- creator without BusinessContext

## Business

- business with BusinessContext

---

# 44. REGRESSION TESTING
All Days 1–13 tests must continue passing.

Do not break:

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
- ContentDraftVariation
- AI Orchestrator
- AI Router
- AI Provider abstraction

---

# 45. DATABASE MIGRATION
Create an Alembic migration for:

content_evaluations

content_evaluation_findings

Include:

- foreign keys
- indexes
- constraints
- timestamps
Follow existing migration conventions.

---

# 46. AI METADATA
Keep provider information as top-level fields:

- generation_source
- ai_provider
- ai_model
- prompt_version
Do not duplicate these values inside metadata.

Metadata should contain only additional extensible information.

---

# 47. PROMPT VERSIONING
Use a fixed application-level prompt version such as:

content_evaluation_v1

Do not allow the client to submit a prompt version.

The server records the actual version used.

---

# 48. ARCHITECTURAL CONSTRAINTS
Continue using:

FastAPI
SQLAlchemy
PostgreSQL
Alembic
Pydantic

Architecture:

Router
↓
Service
↓
Repository
↓
SQLAlchemy

AI:

EvaluationService
↓
AI Orchestrator
↓
AI Router
↓
AI Provider
↓
Model

Do not introduce:

- LangChain
- LangGraph
- microservices
- new AI abstraction
- new model router
- direct provider SDK imports in services
- generic /ai/generate endpoint

---

# 49. PRODUCT VALUE
Day 14 should strengthen the product's core differentiator.

A generic AI writer asks:

> "What should I write?"
AI Content Studio should increasingly answer:

> "This is what you should create."
Then:

> "Here is the brief."
Then:

> "Here are several executions."
Then:

> "This execution scores 82% against your strategy because..."
That is strategic content intelligence, not just generation.

---

# 50. FINAL DAY 14 ARCHITECTURE
The architecture becomes:

ContentProfile
↓
Content Intelligence
↓
Content Opportunity
↓
Content Brief
↓
Content Draft
↓
Content Draft Variations
↓
Content Evaluation
↓
Quality Findings
↓
User Decision
↓
Future Creation / Revision / Publish

AI path:

ContentDraft
↓
ContentEvaluationService
↓
AI Orchestrator
↓
AI Router
↓
AI Provider
↓
Structured Evaluation
↓
Application Scoring
↓
ContentEvaluation

Learning remains future:

Publish
↓
Measure
↓
Performance Intelligence
↓
Learning
↓
Content Intelligence

# ==================================================
END OF DAY 14 SPECIFICATION