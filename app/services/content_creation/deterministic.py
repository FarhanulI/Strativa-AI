from app.models.content_brief import ContentBrief
from app.schemas.content_draft import ContentCreationLLMResult


class DeterministicContentCreator:
    def create(self, brief: ContentBrief) -> ContentCreationLLMResult:
        angle = brief.angle or brief.core_message or brief.strategic_rationale
        points = brief.key_points or []
        body_parts = [angle]
        if points:
            body_parts.append("\n".join(points))
        if brief.supporting_context:
            body_parts.append("\n".join(brief.supporting_context))
        return ContentCreationLLMResult(
            title=brief.title,
            hook=self._hook(brief),
            body="\n\n".join(part for part in body_parts if part),
            cta=self._cta(brief.cta_strategy),
        )

    @staticmethod
    def _hook(brief: ContentBrief) -> str:
        direction = brief.big_idea or brief.angle or brief.core_message
        return direction.strip() if direction else brief.title

    @staticmethod
    def _cta(strategy: str | None) -> str | None:
        if not strategy:
            return None
        return f"{strategy.capitalize()}."
