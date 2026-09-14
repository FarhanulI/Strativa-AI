from typing import Any

from app.schemas.intelligence_analysis import IntelligenceAnalysisLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AITask


class IntelligenceReasoner:
    """Generic LLM reasoning call shared by Brand/Audience/Market analysis.

    Mirrors `app.services.llm.performance_reasoner.PerformanceReasoner`'s
    shape (system prompt + stringified context dict -> structured result via
    the AI Router) but is parameterized by task and prompt version instead
    of being one class per domain, per the day-16 "shared module" guidance.
    """

    def __init__(self, router: AIRouter, task: AITask, prompt_version: str):
        self.router = router
        self.task = task
        self.prompt_version = prompt_version

    async def reason(self, *, system_prompt: str, context: dict[str, Any]) -> AIResult:
        request = AIRequest(
            task=self.task,
            system_prompt=system_prompt,
            user_prompt=str(context),
            response_model=IntelligenceAnalysisLLMResult,
        )
        return await self.router.generate_structured(request)
