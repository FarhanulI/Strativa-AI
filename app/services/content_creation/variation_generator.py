from app.models.content_brief import ContentBrief
from app.models.content_draft import ContentDraft
from app.models.content_draft_variation import VariationType
from app.schemas.content_draft_variation import ContentVariationLLMResult
from app.services.ai.router import AIResult, AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AICapability, AITask
from app.services.content_creation.variation_prompts import VARIATION_SYSTEM_PROMPT

_TASK_BY_TYPE = {
    VariationType.HOOK: AITask.HOOK_GENERATION,
    VariationType.CAPTION: AITask.CAPTION_GENERATION,
}


class ContentDraftVariationGenerator:
    def __init__(self, router: AIRouter | None = None):
        self.router = router or AIRouter()

    async def generate(
        self,
        variation_type: VariationType,
        count: int,
        brief: ContentBrief,
        draft: ContentDraft,
    ) -> tuple[ContentVariationLLMResult, AIResult]:
        request = AIRequest(
            task=_TASK_BY_TYPE[variation_type],
            system_prompt=VARIATION_SYSTEM_PROMPT,
            user_prompt=str(self._context(variation_type, count, brief, draft)),
            response_model=ContentVariationLLMResult,
            required_capabilities={
                AICapability.TEXT_GENERATION,
                AICapability.STRUCTURED_OUTPUT,
                AICapability.REASONING,
            },
        )
        result = await self.router.generate_structured(request)
        output = ContentVariationLLMResult.model_validate(result.output)
        return output, result

    @staticmethod
    def _context(
        variation_type: VariationType, count: int, brief: ContentBrief, draft: ContentDraft
    ) -> dict[str, object]:
        context: dict[str, object] = {
            "variation_type": variation_type.value,
            "count": count,
            "objective": brief.target_objective.value,
            "topic": brief.title,
            "strategic_angle": brief.angle,
            "target_emotion": brief.tone,
            "key_message": brief.core_message,
            "cta_strategy": brief.cta_strategy,
            "recommended_format": brief.recommended_format,
            "platform": draft.platform,
            "existing_hook": draft.hook,
        }
        if variation_type == VariationType.CAPTION:
            context["existing_body"] = draft.body
            context["existing_cta"] = draft.cta
        return context
