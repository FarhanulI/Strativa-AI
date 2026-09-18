"""Step-wise onboarding: progressively builds a workspace's first
ContentProfile (type=creator) across five independently-persisted steps.

Reuses ContentProfileService/Repository, AudienceIntelligenceService,
PainPointService, AudienceQuestionService, and BrandService for all
actual persistence -- this module never writes to those tables directly,
per docs/development/day-22.md.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence, AudienceQuestion, PainPoint
from app.models.brand import Brand
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace, WorkspaceOnboardingStatus
from app.onboarding.schemas import (
    OnboardingAudienceRequest,
    OnboardingBrandRequest,
    OnboardingGoalsRequest,
    OnboardingIdentityRequest,
    OnboardingPlatformsRequest,
)
from app.repositories.content_profile import ContentProfileRepository
from app.services.audience_intelligence import AudienceIntelligenceService
from app.services.audience_question import AudienceQuestionService
from app.services.brand import BrandService
from app.services.content_profile import ContentProfileService
from app.services.pain_point import PainPointService


class OnboardingIdentityRequiredError(Exception):
    """Raised when a later onboarding step is submitted before the
    identity step has created the workspace's ContentProfile -- every
    other domain (audience, goals, brand, platforms) hangs off that
    profile, so identity must come first.
    """


class OnboardingIncompleteError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Onboarding is incomplete: missing {', '.join(missing)}")


class OnboardingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.profile_repository = ContentProfileRepository(session)
        self.profile_service = ContentProfileService(session)
        self.audience_service = AudienceIntelligenceService(session)
        self.pain_point_service = PainPointService(session)
        self.question_service = AudienceQuestionService(session)
        self.brand_service = BrandService(session)

    async def _get_profile(self, workspace_id: UUID) -> ContentProfile | None:
        profiles = await self.profile_repository.list_by_workspace(
            workspace_id=workspace_id, skip=0, limit=1
        )
        return profiles[0] if profiles else None

    async def _require_profile(self, workspace_id: UUID) -> ContentProfile:
        profile = await self._get_profile(workspace_id)
        if profile is None:
            raise OnboardingIdentityRequiredError(
                "Complete the identity step before providing this information"
            )
        return profile

    def _mark_in_progress(self, workspace: Workspace) -> None:
        if workspace.onboarding_status == WorkspaceOnboardingStatus.NOT_STARTED:
            workspace.onboarding_status = WorkspaceOnboardingStatus.IN_PROGRESS

    async def update_identity(
        self, workspace: Workspace, payload: OnboardingIdentityRequest
    ) -> ContentProfile:
        profile = await self._get_profile(workspace.id)
        if profile is None:
            profile = await self.profile_service.create(
                workspace_id=workspace.id,
                type=ContentProfileType.CREATOR,
                name=payload.name,
                positioning=payload.positioning,
                primary_niche=payload.primary_niche,
                topics=payload.topics,
                expertise=payload.expertise,
            )
        else:
            profile = await self.profile_service.update(
                profile_id=profile.id,
                workspace_id=workspace.id,
                name=payload.name,
                positioning=payload.positioning,
                primary_niche=payload.primary_niche,
                topics=payload.topics,
                expertise=payload.expertise,
            )

        self._mark_in_progress(workspace)
        await self.session.commit()
        return profile

    async def update_audience(
        self, workspace: Workspace, payload: OnboardingAudienceRequest
    ) -> tuple[AudienceIntelligence, list[PainPoint], list[AudienceQuestion]]:
        profile = await self._require_profile(workspace.id)
        audience = await self.audience_service.get(profile.id, workspace.id)

        psychographics = (
            dict(audience.psychographics) if audience and audience.psychographics else {}
        )
        if payload.interests is not None:
            psychographics["interests"] = payload.interests
        psychographics_value = psychographics or None

        if audience is None:
            audience = await self.audience_service.create(
                profile_id=profile.id,
                workspace_id=workspace.id,
                summary=payload.target_audience_description,
                psychographics=psychographics_value,
            )
        else:
            await self.audience_service.update(
                profile_id=profile.id,
                workspace_id=workspace.id,
                summary=payload.target_audience_description,
                psychographics=psychographics_value,
            )
            audience = await self.audience_service.get(profile.id, workspace.id)

        if payload.pain_points is not None:
            for existing_pp in await self.pain_point_service.list(audience.id, workspace.id):
                await self.pain_point_service.delete(audience.id, existing_pp.id, workspace.id)
            for title in payload.pain_points:
                await self.pain_point_service.create(audience.id, workspace.id, title)

        if payload.questions is not None:
            for existing_q in await self.question_service.list(audience.id, workspace.id):
                await self.question_service.delete(audience.id, existing_q.id, workspace.id)
            for question_text in payload.questions:
                await self.question_service.create(audience.id, workspace.id, question_text)

        self._mark_in_progress(workspace)
        await self.session.commit()

        pain_points = await self.pain_point_service.list(audience.id, workspace.id)
        questions = await self.question_service.list(audience.id, workspace.id)
        return audience, pain_points, questions

    async def update_goals(
        self, workspace: Workspace, payload: OnboardingGoalsRequest
    ) -> ContentProfile:
        profile = await self._require_profile(workspace.id)
        profile = await self.profile_service.update(
            profile_id=profile.id,
            workspace_id=workspace.id,
            goals=[goal.value for goal in payload.goals],
        )
        self._mark_in_progress(workspace)
        await self.session.commit()
        return profile

    async def update_brand(self, workspace: Workspace, payload: OnboardingBrandRequest) -> Brand:
        profile = await self._require_profile(workspace.id)
        brand = await self.brand_service.get(profile.id, workspace.id)

        guidelines = (
            dict(brand.messaging_guidelines) if brand and brand.messaging_guidelines else {}
        )
        if payload.style is not None:
            guidelines["style"] = payload.style
        if payload.things_to_avoid is not None:
            guidelines["things_to_avoid"] = payload.things_to_avoid
        messaging_guidelines = guidelines or None

        tone = {"tone_words": payload.tone} if payload.tone is not None else None

        if brand is None:
            brand = await self.brand_service.create(
                profile_id=profile.id,
                workspace_id=workspace.id,
                tone=tone,
                messaging_guidelines=messaging_guidelines,
            )
        else:
            await self.brand_service.update(
                profile_id=profile.id,
                workspace_id=workspace.id,
                tone=tone,
                messaging_guidelines=messaging_guidelines,
            )
            brand = await self.brand_service.get(profile.id, workspace.id)

        self._mark_in_progress(workspace)
        await self.session.commit()
        return brand

    async def update_platforms(
        self, workspace: Workspace, payload: OnboardingPlatformsRequest
    ) -> ContentProfile:
        profile = await self._require_profile(workspace.id)
        profile = await self.profile_service.update(
            profile_id=profile.id,
            workspace_id=workspace.id,
            platforms=[platform.value for platform in payload.platforms],
        )
        self._mark_in_progress(workspace)
        await self.session.commit()
        return profile

    async def get_state(self, workspace: Workspace) -> dict:
        profile = await self._get_profile(workspace.id)
        identity = audience_state = goals_state = brand_state = platforms_state = None

        if profile is not None:
            identity = {
                "profile_id": profile.id,
                "name": profile.name,
                "positioning": profile.positioning,
                "primary_niche": profile.primary_niche,
                "topics": profile.topics,
                "expertise": profile.expertise,
            }
            if profile.goals:
                goals_state = {"goals": profile.goals}
            if profile.platforms:
                platforms_state = {"platforms": profile.platforms}

            audience = await self.audience_service.get(profile.id, workspace.id)
            if audience is not None:
                pain_points = await self.pain_point_service.list(audience.id, workspace.id)
                questions = await self.question_service.list(audience.id, workspace.id)
                audience_state = {
                    "target_audience_description": audience.summary,
                    "interests": (audience.psychographics or {}).get("interests"),
                    "pain_points": [pp.title for pp in pain_points],
                    "questions": [q.question for q in questions],
                }

            brand = await self.brand_service.get(profile.id, workspace.id)
            if brand is not None:
                brand_state = {
                    "tone": (brand.tone or {}).get("tone_words"),
                    "style": (brand.messaging_guidelines or {}).get("style"),
                    "things_to_avoid": (brand.messaging_guidelines or {}).get("things_to_avoid"),
                }

        return {
            "onboarding_status": workspace.onboarding_status,
            "identity": identity,
            "audience": audience_state,
            "goals": goals_state,
            "brand": brand_state,
            "platforms": platforms_state,
        }

    async def complete(self, workspace: Workspace) -> ContentProfile:
        profile = await self._get_profile(workspace.id)
        missing: list[str] = []

        if profile is None:
            missing.append("identity")
        else:
            if not profile.positioning:
                missing.append("identity.positioning")
            if not profile.primary_niche:
                missing.append("identity.primary_niche")
            if not profile.topics:
                missing.append("identity.topics")
            if not profile.expertise:
                missing.append("identity.expertise")
            if not profile.goals:
                missing.append("goals")
            if not profile.platforms:
                missing.append("platforms")

            audience = await self.audience_service.get(profile.id, workspace.id)
            if audience is None or not audience.summary:
                missing.append("audience.target_audience_description")
            elif audience is not None:
                pain_points = await self.pain_point_service.list(audience.id, workspace.id)
                questions = await self.question_service.list(audience.id, workspace.id)
                if not pain_points and not questions:
                    missing.append("audience.pain_points_or_questions")

            brand = await self.brand_service.get(profile.id, workspace.id)
            if brand is None or not brand.tone:
                missing.append("brand.tone")

        if missing:
            raise OnboardingIncompleteError(missing)

        workspace.onboarding_status = WorkspaceOnboardingStatus.COMPLETED
        await self.session.commit()
        return profile
