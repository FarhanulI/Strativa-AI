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

    async def reason(self, *, context: dict[str, Any]) -> AIResult:
        request = AIRequest(
            task=AITask.STRATEGIC_SYNTHESIS,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=str(context),
            response_model=ContentIntelligenceSynthesisLLMResult,
            required_capabilities={
                AICapability.REASONING,
                AICapability.STRUCTURED_OUTPUT,
                AICapability.LONG_CONTEXT,
            },
        )
        return await self.router.generate_structured(request)
