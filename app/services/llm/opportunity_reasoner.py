from typing import Any

from app.schemas.content_opportunity import OpportunityRationaleLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AICapability, AITask

SYSTEM_PROMPT = (
    "You are explaining the strategic rationale behind an already-computed content "
    "opportunity score for a profile. The score, its components, and the opportunity's "
    "priority are fixed and must never be restated as if you produced them -- your job is "
    "only to explain, in natural language, why this opportunity matters for this specific "
    "profile right now. Ground your explanation in the provided score components and the "
    "profile's current cross-domain intelligence synthesis. Do not invent facts about the "
    "profile, audience, market, or performance that are not present in the provided "
    "context. Use likely, suggests, appears, or may indicate for interpretive claims. "
    "If the context includes an influencing_learning, explicitly reference that "
    "durable performance pattern as part of why this opportunity matters -- it "
    "represents evidence from the profile's own content history, not a guess."
)

PROMPT_VERSION = "opportunity_reasoning_v1"


class OpportunityReasoner:
    """The `opportunity_reasoning` AI task's reasoning call: deterministic score
    components + the profile's current ContentIntelligenceSynthesis -> a
    natural-language strategic_rationale via the AI Router. Mirrors
    `app.services.llm.intelligence_reasoner.IntelligenceReasoner`'s shape.
    """

    def __init__(self, router: AIRouter):
        self.router = router
        self.prompt_version = PROMPT_VERSION

    async def reason(self, *, context: dict[str, Any]) -> AIResult:
        request = AIRequest(
            task=AITask.OPPORTUNITY_REASONING,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=str(context),
            response_model=OpportunityRationaleLLMResult,
            required_capabilities={AICapability.REASONING, AICapability.STRUCTURED_OUTPUT},
        )
        return await self.router.generate_structured(request)
