from app.models.content_brief import ContentBrief
from app.schemas.content_draft import ContentCreationLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AICapability, AITask
from app.services.content_creation.prompts import SYSTEM_PROMPT


class ContentCreator:
    def __init__(self, router: AIRouter | None = None):
        self.router = router or AIRouter()

    async def create(self, brief: ContentBrief) -> tuple[ContentCreationLLMResult, AIResult]:
        request = AIRequest(
            task=AITask.CONTENT_CREATION,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=str(self._brief_context(brief)),
            response_model=ContentCreationLLMResult,
            required_capabilities={
                AICapability.TEXT_GENERATION,
                AICapability.STRUCTURED_OUTPUT,
                AICapability.REASONING,
            },
        )
        result = await self.router.generate_structured(request)
        output = ContentCreationLLMResult.model_validate(result.output)
        return output, result

    @staticmethod
    def _brief_context(brief: ContentBrief) -> dict[str, object]:
        return {
            "platform": brief.recommended_platform,
            "format": brief.recommended_format,
            "objective": brief.target_objective.value,
            "topic": brief.title,
            "strategic_angle": brief.angle,
            "big_idea": brief.big_idea,
            "hook_direction": brief.core_message,
            "target_emotion": brief.tone,
            "story_structure": brief.supporting_context or [],
            "key_message": brief.core_message,
            "cta_strategy": brief.cta_strategy,
            "key_points": brief.key_points or [],
            "supporting_context": brief.supporting_context or [],
            "recommended_length": brief.recommended_length,
            "voice_guidelines": brief.voice_guidelines,
        }
