from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceQuestion, Desire, PainPoint, Persona
from app.models.content_brief import BriefStatus, ContentBrief, GenerationSource
from app.models.content_opportunity import ContentOpportunity
from app.repositories.content_brief import ContentBriefRepository
from app.repositories.content_opportunity import ContentOpportunityRepository
from app.repositories.content_profile import ContentProfileRepository
from app.services.ai.router import AIRouter
from app.services.brief.composer import BriefComposer


class ContentBriefService:
    def __init__(self, session: AsyncSession, router: AIRouter | None = None):
        self.session = session
        self.repository = ContentBriefRepository(session)
        self.opportunity_repository = ContentOpportunityRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.composer = BriefComposer(router)

    async def create(
        self, profile_id: UUID, workspace_id: UUID, opportunity_id: UUID, **values: Any
    ) -> ContentBrief:
        profile = await self._verify_profile(profile_id, workspace_id)
        opportunity = await self.opportunity_repository.get_by_id(profile_id, opportunity_id)
        if not opportunity:
            raise ValueError("Content opportunity not found")
        references = await self._references(profile_id, values)
        mode = values.get("composition_mode", "compose")
        if mode == "manual":
            if not values.get("title") or not values.get("core_message"):
                raise ValueError("Manual briefs require title and core_message")
            brief = ContentBrief(
                profile_id=profile_id,
                opportunity_id=opportunity_id,
                title=values["title"],
                core_message=values["core_message"],
                strategic_rationale=opportunity.strategic_rationale,
                target_objective=values.get("target_objective") or opportunity.target_objective,
                recommended_format=values.get("recommended_format")
                or opportunity.recommended_format,
                recommended_platform=values.get("recommended_platform", "other"),
                generation_source=GenerationSource.MANUAL,
                status=BriefStatus.DRAFT,
            )
        else:
            brief = self.composer.compose_deterministically(
                profile=profile, opportunity=opportunity, target_persona=references.get("persona")
            )
            if values.get("use_ai"):
                try:
                    brief, metadata = await self.composer.enrich(
                        profile=profile, opportunity=opportunity, brief=brief
                    )
                    brief.generation_source = GenerationSource.AI_ASSISTED
                    brief.brief_metadata = {
                        "composition": self._composition_metadata(opportunity, values),
                        "ai": {
                            "provider": metadata.provider,
                            "model": metadata.model,
                            "prompt_version": self.composer.prompt_version,
                        },
                    }
                except Exception:
                    brief.generation_source = GenerationSource.DETERMINISTIC
            else:
                brief.generation_source = GenerationSource.DETERMINISTIC
        self._apply_client_values(brief, values, references)
        if brief.brief_metadata is None:
            brief.brief_metadata = {"composition": self._composition_metadata(opportunity, values)}
        await self.repository.create(brief)
        await self.session.commit()
        return brief

    async def get(
        self, profile_id: UUID, brief_id: UUID, workspace_id: UUID
    ) -> ContentBrief | None:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.get_by_id(profile_id, brief_id)

    async def list(
        self, profile_id: UUID, workspace_id: UUID, **filters: Any
    ) -> list[ContentBrief]:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.list_by_profile(profile_id, **filters)

    async def list_by_opportunity(
        self, profile_id: UUID, opportunity_id: UUID, workspace_id: UUID, **filters: Any
    ) -> list[ContentBrief]:
        await self._verify_profile(profile_id, workspace_id)
        if not await self.opportunity_repository.get_by_id(profile_id, opportunity_id):
            raise ValueError("Content opportunity not found")
        return await self.repository.list_by_opportunity(profile_id, opportunity_id, **filters)

    async def update(
        self, profile_id: UUID, brief_id: UUID, workspace_id: UUID, **values: Any
    ) -> ContentBrief | None:
        await self._verify_profile(profile_id, workspace_id)
        brief = await self.repository.get_by_id(profile_id, brief_id)
        if not brief:
            return None
        if values.get("status") is not None:
            self._validate_status_transition(brief.status, values["status"])
        references = await self._references(profile_id, values)
        self._apply_client_values(brief, values, references)
        await self.repository.update(brief)
        await self.session.commit()
        return brief

    async def delete(self, profile_id: UUID, brief_id: UUID, workspace_id: UUID) -> bool:
        await self._verify_profile(profile_id, workspace_id)
        brief = await self.repository.get_by_id(profile_id, brief_id)
        if not brief:
            return False
        await self.repository.delete(brief)
        await self.session.commit()
        return True

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    async def _references(self, profile_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        from app.models.audience_intelligence import AudienceIntelligence

        refs = {
            "persona": (Persona, values.get("target_persona_id")),
            "pain_point": (PainPoint, values.get("target_pain_point_id")),
            "desire": (Desire, values.get("target_desire_id")),
            "audience_question": (AudienceQuestion, values.get("target_audience_question_id")),
        }
        result: dict[str, Any] = {}
        for name, (model, reference_id) in refs.items():
            if reference_id is None:
                continue
            query = (
                select(model)
                .join(AudienceIntelligence)
                .where(
                    model.id == reference_id, AudienceIntelligence.content_profile_id == profile_id
                )
            )
            item = (await self.session.execute(query)).scalar_one_or_none()
            if not item:
                raise ValueError(f"{name.replace('_', ' ').title()} not found")
            result[name] = item
        return result

    @staticmethod
    def _apply_client_values(
        brief: ContentBrief, values: dict[str, Any], references: dict[str, Any]
    ):
        fields = (
            "title",
            "core_message",
            "angle",
            "big_idea",
            "target_objective",
            "recommended_format",
            "recommended_platform",
            "recommended_length",
            "tone",
            "voice_guidelines",
            "cta_strategy",
            "key_points",
            "supporting_context",
            "success_criteria",
        )
        for field in fields:
            if values.get(field) is not None:
                setattr(brief, field, values[field])
        if values.get("status") is not None:
            brief.status = values["status"]
        for field, key in (
            ("target_persona_id", "persona"),
            ("target_pain_point_id", "pain_point"),
            ("target_desire_id", "desire"),
            ("target_audience_question_id", "audience_question"),
        ):
            if field in values:
                setattr(brief, field, values[field])
            if key in references:
                setattr(brief, field, references[key].id)

    @staticmethod
    def _validate_status_transition(current: BriefStatus, target: BriefStatus):
        allowed = {
            BriefStatus.DRAFT: {BriefStatus.READY},
            BriefStatus.READY: {BriefStatus.APPROVED},
            BriefStatus.APPROVED: {BriefStatus.ARCHIVED},
            BriefStatus.ARCHIVED: set(),
        }
        if target != current and target not in allowed[current]:
            raise ValueError("Invalid brief status transition")

    @staticmethod
    def _composition_metadata(
        opportunity: ContentOpportunity, values: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "inherited_objective": values.get("target_objective") is None,
            "inherited_format": values.get("recommended_format") is None,
            "signal_type": opportunity.source_signal.value,
            "source_signal_id": str(
                opportunity.market_signal_id
                or opportunity.audience_signal_id
                or opportunity.performance_insight_id
            )
            if (
                opportunity.market_signal_id
                or opportunity.audience_signal_id
                or opportunity.performance_insight_id
            )
            else None,
            "persona_id": str(values["target_persona_id"])
            if values.get("target_persona_id")
            else None,
            "pain_point_id": str(values["target_pain_point_id"])
            if values.get("target_pain_point_id")
            else None,
            "desire_id": str(values["target_desire_id"])
            if values.get("target_desire_id")
            else None,
            "audience_question_id": str(values["target_audience_question_id"])
            if values.get("target_audience_question_id")
            else None,
        }
