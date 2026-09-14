from typing import Any

from app.schemas.content_intelligence_synthesis import ContentIntelligenceSynthesisLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AICapability, AITask

SYSTEM_PROMPT = (
    "You are producing a strategic synthesis across a content profile's Brand, Audience, "
    "Market, and Performance intelligence. Combine whichever of those component analyses "
    "are available into genuine cross-signal reasoning about what they mean together for "
    "this specific profile -- do not simply restate or list each input in isolation. Only "
    "make claims grounded in the provided analyses. If a domain is marked unavailable, note "
    "that gap rather than inventing what it might say. Use likely, suggests, appears, or may "
    "indicate for interpretive claims."
)

# Appended only when `cold_start` is True: Brand/Audience/Market are all
# grounded and Performance is absent specifically because the profile has
# published nothing yet (see app.content_intelligence.grounding). This is
# the activation-framing requirement from the day-16/17 cold-start patch --
# the summary must read as an inspiring first-content recommendation, not a
# degraded or apologetic result.
COLD_START_PROMPT_ADDENDUM = (
    "This profile has not published any content yet, so it has no Performance "
    "Intelligence -- that is expected and normal for a brand-new profile, not a "
    "limitation or a data gap, and must not be framed as one. Do not apologize for "
    "or caveat the absence of performance history. Instead, produce an opportunity/"
    "activation-focused summary describing what a strong first piece of content "
    "should be, grounded only in the available Brand, Audience, and Market "
    "analyses. Never fabricate, imply, or reference performance data, metrics, or "
    "results that do not exist."
)

PROMPT_VERSION = "strategic_synthesis_v1"


class SynthesisReasoner:
    """The `strategic_synthesis` AI task's reasoning call: whatever component
    analyses are available -> genuine cross-signal reasoning via the AI
    Router, never a restatement of the inputs. Mirrors
    `app.services.llm.intelligence_reasoner.IntelligenceReasoner`'s shape.
    """

    def __init__(self, router: AIRouter):
        self.router = router
        self.prompt_version = PROMPT_VERSION

    async def reason(self, *, context: dict[str, Any], cold_start: bool = False) -> AIResult:
        system_prompt = SYSTEM_PROMPT
        if cold_start:
            system_prompt = f"{SYSTEM_PROMPT} {COLD_START_PROMPT_ADDENDUM}"

        request = AIRequest(
            task=AITask.STRATEGIC_SYNTHESIS,
            system_prompt=system_prompt,
            user_prompt=str(context),
            response_model=ContentIntelligenceSynthesisLLMResult,
            required_capabilities={
                AICapability.REASONING,
                AICapability.STRUCTURED_OUTPUT,
                AICapability.LONG_CONTEXT,
            },
        )
        return await self.router.generate_structured(request)
