from typing import Any

from app.models.content_brief import ContentBrief
from app.models.content_opportunity import ContentOpportunity, TargetObjective
from app.schemas.content_brief import BriefCompositionLLMResult
from app.services.ai.router import AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AITask


class BriefComposer:
    prompt_version = "content_brief_v1"

    def __init__(self, router: AIRouter | None = None):
        self.router = router or AIRouter()

    def compose_deterministically(
        self,
        *,
        profile: Any,
        opportunity: ContentOpportunity,
        target_persona: Any | None = None,
    ) -> ContentBrief:
        source_summary = self._source_summary(opportunity)
        tone = self._brand_value(profile, "tone") or "clear, confident, on-brand"
        voice = self._brand_value(profile, "voice")
        return ContentBrief(
            profile_id=profile.id,
            opportunity_id=opportunity.id,
            title=f"{opportunity.recommended_format or 'content'} — {source_summary}",
            core_message=self._one_sentence(opportunity.strategic_rationale),
            strategic_rationale=opportunity.strategic_rationale,
            target_objective=opportunity.target_objective,
            recommended_format=opportunity.recommended_format,
            recommended_platform="other",
            tone=tone,
            voice_guidelines=voice,
            cta_strategy=self._cta_strategy(opportunity.target_objective),
            key_points=[
                f"What the signal represents: {source_summary}.",
                f"Why it is relevant to {profile.name}: {opportunity.strategic_rationale}",
                f"Which objective it serves: {opportunity.target_objective.value}.",
            ],
            success_criteria=[
                "Audience remains engaged past the hook",
                "Audience takes the recommended CTA",
                "Content reinforces the profile's positioning",
            ],
        )

    async def enrich(self, *, profile: Any, opportunity: ContentOpportunity, brief: ContentBrief):
        request = AIRequest(
            task=AITask.CONTENT_CONCEPT_GENERATION,
            system_prompt=(
                "Produce strategic direction only. Use only the provided profile and signal "
                "information. Do not invent demographics, products, services, offers, "
                "performance data, statistics, external facts, final captions, final hooks, "
                "scripts, or finished creative."
            ),
            user_prompt=str(
                {
                    "profile": {
                        "positioning": profile.positioning,
                        "topics": profile.topics or [],
                        "expertise": profile.expertise or [],
                        "brand_voice": brief.voice_guidelines,
                    },
                    "opportunity": {
                        "source": opportunity.source_signal.value,
                        "title": opportunity.title,
                        "rationale": opportunity.strategic_rationale,
                        "objective": opportunity.target_objective.value,
                        "format": opportunity.recommended_format,
                    },
                }
            ),
            response_model=BriefCompositionLLMResult,
        )
        result = await self.router.generate_structured(request)
        output = BriefCompositionLLMResult.model_validate(result.output)
        brief.angle = output.angle
        brief.big_idea = output.big_idea
        brief.voice_guidelines = output.voice_guidelines
        brief.key_points = output.key_points
        brief.supporting_context = output.supporting_context
        return brief, result.metadata

    @staticmethod
    def _source_summary(opportunity: ContentOpportunity) -> str:
        if opportunity.market_signal:
            return opportunity.market_signal.title
        if opportunity.audience_signal:
            return (
                opportunity.audience_signal.question
                or opportunity.audience_signal.topic
                or opportunity.title
            )
        if opportunity.performance_insight:
            return opportunity.performance_insight.summary
        return opportunity.title

    @staticmethod
    def _one_sentence(text: str) -> str:
        sentence = text.strip().split(".", 1)[0].strip()
        return f"{sentence}." if sentence else text

    @staticmethod
    def _cta_strategy(objective: TargetObjective) -> str:
        return {
            TargetObjective.GROWTH: "encourage sharing",
            TargetObjective.AUTHORITY: "encourage saving / following",
            TargetObjective.LEAD_GEN: "encourage conversation / DM",
            TargetObjective.SALES: "encourage click / purchase",
        }[objective]

    @staticmethod
    def _brand_value(profile: Any, field: str) -> str | None:
        brand = getattr(profile, "brand", None)
        value = getattr(brand, field, None) if brand else None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return ", ".join(f"{key}: {item}" for key, item in value.items())
        return None
