from typing import Any

from app.schemas.learning import LearningExplanationLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AICapability, AITask

SYSTEM_PROMPT = (
    "You are explaining an already-computed statistical performance pattern (a "
    "'learning') for a content profile. The dimension, dimension value, sample size, "
    "and confidence level are fixed and were computed deterministically -- your job is "
    "only to explain, in plain natural language, why this pattern is strategically "
    "useful going forward. Ground your explanation strictly in the provided pattern "
    "description and supporting evidence. Do not invent facts, numbers, or causes that "
    "are not present in the provided context. Use likely, suggests, appears, or may "
    "indicate for interpretive claims."
)

PROMPT_VERSION = "learning_explanation_v1"


class LearningExplainer:
    """The `learning_explanation` AI task: a deterministically-extracted
    pattern + its supporting evidence -> a natural-language explanation via
    the AI Router. Enriches `Learning.explanation` only -- never
    `pattern_description`, `dimension`, `dimension_value`, or
    `confidence_level`, which stay fully deterministic.
    """

    def __init__(self, router: AIRouter):
        self.router = router
        self.prompt_version = PROMPT_VERSION

    async def explain(self, *, context: dict[str, Any]) -> AIResult:
        request = AIRequest(
            task=AITask.LEARNING_EXPLANATION,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=str(context),
            response_model=LearningExplanationLLMResult,
            required_capabilities={AICapability.REASONING, AICapability.STRUCTURED_OUTPUT},
        )
        return await self.router.generate_structured(request)
