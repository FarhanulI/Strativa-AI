from typing import Any

from app.schemas.content_performance import PerformanceInsightLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AITask


class PerformanceReasoner:
    prompt_version = "performance_insight_v1"

    def __init__(self, router: AIRouter):
        self.router = router

    async def reason(
        self, *, profile: Any, content: Any, analysis: Any
    ) -> AIResult:
        system = (
            "Only make claims supported by provided evidence. Do not invent metrics or "
            "demographics. Do not claim causation when evidence only shows correlation. "
            "Use likely, suggests, appears, or may indicate. Focus on reusable strategic "
            "learning and recommend an actionable next experiment."
        )
        user = {
            "profile": {
                "positioning": profile.positioning,
                "topics": profile.topics or [],
                "expertise": profile.expertise or [],
                "goals": profile.goals or [],
            },
            "content": {"topic": content.topic, "format": content.format, "hook": content.hook},
            "analysis": analysis.evidence,
        }
        request = AIRequest(
            task=AITask.PERFORMANCE_REASONING,
            system_prompt=system,
            user_prompt=str(user),
            response_model=PerformanceInsightLLMResult,
        )
        return await self.router.generate_structured(request)
