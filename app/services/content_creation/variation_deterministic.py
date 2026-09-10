from app.models.content_brief import ContentBrief
from app.models.content_draft import ContentDraft
from app.models.content_draft_variation import VariationType
from app.schemas.content_draft_variation import ContentVariationLLMItem

_HOOK_TEMPLATES = [
    "Here's what most people get wrong about {topic}.",
    "Before you create another {format}, understand this about {topic}.",
    "If you're trying to {objective}, start with this.",
    "{topic}: the part everyone skips.",
    "A quick reframe on {topic} before you scroll past.",
]

_CAPTION_TEMPLATES = [
    "{key_message} {cta}",
    "Let's talk about {topic}. {key_message} {cta}",
    "{angle} {key_message} {cta}",
]


class DeterministicVariationGenerator:
    def generate(
        self,
        variation_type: VariationType,
        count: int,
        brief: ContentBrief,
        draft: ContentDraft,
    ) -> list[ContentVariationLLMItem]:
        if variation_type == VariationType.HOOK:
            return self._hooks(count, brief, draft)
        return self._captions(count, brief, draft)

    def _hooks(
        self, count: int, brief: ContentBrief, draft: ContentDraft
    ) -> list[ContentVariationLLMItem]:
        topic = brief.title
        objective = brief.target_objective.value.replace("_", " ")
        variations = []
        for index in range(count):
            template = _HOOK_TEMPLATES[index % len(_HOOK_TEMPLATES)]
            content = template.format(topic=topic, format=draft.format, objective=objective)
            variations.append(
                ContentVariationLLMItem(
                    content=content,
                    rationale=(
                        f"Deterministic hook template #{index + 1} built from the "
                        "brief topic and objective."
                    ),
                )
            )
        return variations

    def _captions(
        self, count: int, brief: ContentBrief, draft: ContentDraft
    ) -> list[ContentVariationLLMItem]:
        key_message = brief.core_message
        angle = brief.angle or ""
        cta = self._cta(brief.cta_strategy)
        variations = []
        for index in range(count):
            template = _CAPTION_TEMPLATES[index % len(_CAPTION_TEMPLATES)]
            content = " ".join(
                template.format(
                    topic=brief.title, key_message=key_message, angle=angle, cta=cta
                ).split()
            )
            variations.append(
                ContentVariationLLMItem(
                    content=content,
                    rationale=(
                        f"Deterministic caption template #{index + 1} preserving the "
                        "brief's key message and CTA strategy."
                    ),
                )
            )
        return variations

    @staticmethod
    def _cta(strategy: str | None) -> str:
        if not strategy:
            return ""
        return f"{strategy.capitalize()}."
