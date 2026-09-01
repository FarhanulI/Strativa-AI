from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence
from app.repositories.audience_intelligence import AudienceIntelligenceRepository
from app.repositories.content_profile import ContentProfileRepository


class AudienceIntelligenceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AudienceIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        summary: str | None = None,
        language: str | None = None,
        geography: str | None = None,
        demographics: dict | None = None,
        psychographics: dict | None = None,
        behaviors: dict | None = None,
        content_preferences: dict | None = None,
    ) -> AudienceIntelligence:
        """
        Create audience intelligence for a content profile.
        Verifies profile exists and belongs to the workspace.
        Prevents duplicate audience intelligence per profile.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")

        existing = await self.repository.get_by_profile(profile_id)
        if existing:
            raise ValueError("Audience intelligence already exists for this content profile.")

        audience_intelligence = AudienceIntelligence(
            content_profile_id=profile_id,
            summary=summary,
            language=language,
            geography=geography,
            demographics=demographics,
            psychographics=psychographics,
            behaviors=behaviors,
            content_preferences=content_preferences,
        )
        await self.repository.create(audience_intelligence)
        await self.session.commit()
        return audience_intelligence

    async def get(self, profile_id: UUID, workspace_id: UUID) -> AudienceIntelligence | None:
        """
        Get audience intelligence for a content profile within a workspace.
        Verifies workspace ownership to prevent cross-tenant access.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        return await self.repository.get_by_profile(profile_id)

    async def update(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        summary: str | None = None,
        language: str | None = None,
        geography: str | None = None,
        demographics: dict | None = None,
        psychographics: dict | None = None,
        behaviors: dict | None = None,
        content_preferences: dict | None = None,
    ) -> AudienceIntelligence | None:
        """
        Update audience intelligence for a content profile.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        audience_intelligence = await self.repository.get_by_profile(profile_id)
        if not audience_intelligence:
            return None

        if summary is not None:
            audience_intelligence.summary = summary
        if language is not None:
            audience_intelligence.language = language
        if geography is not None:
            audience_intelligence.geography = geography
        if demographics is not None:
            audience_intelligence.demographics = demographics
        if psychographics is not None:
            audience_intelligence.psychographics = psychographics
        if behaviors is not None:
            audience_intelligence.behaviors = behaviors
        if content_preferences is not None:
            audience_intelligence.content_preferences = content_preferences

        await self.repository.update(audience_intelligence)
        await self.session.commit()
        return audience_intelligence

    async def delete(self, profile_id: UUID, workspace_id: UUID) -> bool:
        """
        Delete audience intelligence for a content profile.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return False

        audience_intelligence = await self.repository.get_by_profile(profile_id)
        if not audience_intelligence:
            return False

        success = await self.repository.delete(audience_intelligence.id)
        if success:
            await self.session.commit()
        return success
