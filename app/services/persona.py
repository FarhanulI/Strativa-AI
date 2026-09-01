from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import Persona
from app.repositories.audience_intelligence import AudienceIntelligenceRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.persona import PersonaRepository


class PersonaService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PersonaRepository(session)
        self.audience_repository = AudienceIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        name: str,
        description: str | None = None,
        demographics: dict | None = None,
        psychographics: dict | None = None,
        goals: list | None = None,
        pain_points: list | None = None,
        desires: list | None = None,
        behaviors: list | None = None,
        content_preferences: list | None = None,
    ) -> Persona:
        """
        Create a persona within audience intelligence.
        Verifies workspace ownership through content profile.
        """
        audience = await self.audience_repository.get_by_profile(
            await self._get_profile_id_for_audience(audience_intelligence_id)
        )
        if not audience or audience.id != audience_intelligence_id:
            raise ValueError("Audience intelligence not found")

        profile = await self.profile_repository.get_by_id(
            audience.content_profile_id, workspace_id
        )
        if not profile:
            raise ValueError("Workspace access denied")

        persona = Persona(
            audience_intelligence_id=audience_intelligence_id,
            name=name,
            description=description,
            demographics=demographics,
            psychographics=psychographics,
            goals=goals,
            pain_points=pain_points,
            desires=desires,
            behaviors=behaviors,
            content_preferences=content_preferences,
        )
        await self.repository.create(persona)
        await self.session.commit()
        return persona

    async def get(
        self, audience_intelligence_id: UUID, persona_id: UUID, workspace_id: UUID
    ) -> Persona | None:
        """
        Get a specific persona with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        persona = await self.repository.get_by_id(persona_id)
        if not persona or persona.audience_intelligence_id != audience_intelligence_id:
            return None

        return persona

    async def list(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Persona]:
        """
        List personas for audience intelligence with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        return await self.repository.list_by_audience(
            audience_intelligence_id, skip=skip, limit=limit
        )

    async def update(
        self,
        audience_intelligence_id: UUID,
        persona_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        description: str | None = None,
        demographics: dict | None = None,
        psychographics: dict | None = None,
        goals: list | None = None,
        pain_points: list | None = None,
        desires: list | None = None,
        behaviors: list | None = None,
        content_preferences: list | None = None,
    ) -> Persona | None:
        """
        Update a persona.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        persona = await self.repository.get_by_id(persona_id)
        if not persona or persona.audience_intelligence_id != audience_intelligence_id:
            return None

        if name is not None:
            persona.name = name
        if description is not None:
            persona.description = description
        if demographics is not None:
            persona.demographics = demographics
        if psychographics is not None:
            persona.psychographics = psychographics
        if goals is not None:
            persona.goals = goals
        if pain_points is not None:
            persona.pain_points = pain_points
        if desires is not None:
            persona.desires = desires
        if behaviors is not None:
            persona.behaviors = behaviors
        if content_preferences is not None:
            persona.content_preferences = content_preferences

        await self.repository.update(persona)
        await self.session.commit()
        return persona

    async def delete(
        self, audience_intelligence_id: UUID, persona_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Delete a persona.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        persona = await self.repository.get_by_id(persona_id)
        if not persona or persona.audience_intelligence_id != audience_intelligence_id:
            return False

        success = await self.repository.delete(persona_id)
        if success:
            await self.session.commit()
        return success

    async def _verify_workspace_access(
        self, audience_intelligence_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Verify that audience intelligence belongs to the workspace.
        """
        from app.models.audience_intelligence import AudienceIntelligence
        from sqlalchemy import select

        stmt = select(AudienceIntelligence).where(
            AudienceIntelligence.id == audience_intelligence_id
        )
        result = await self.session.execute(stmt)
        audience = result.scalar_one_or_none()

        if not audience:
            raise ValueError("Audience intelligence not found")

        profile = await self.profile_repository.get_by_id(
            audience.content_profile_id, workspace_id
        )
        if not profile:
            raise ValueError("Workspace access denied")

        return True

    async def _get_profile_id_for_audience(self, audience_intelligence_id: UUID) -> UUID:
        """
        Helper to get content_profile_id for an audience_intelligence_id.
        This is a workaround for the circular query issue.
        """
        from sqlalchemy import select

        from app.models.audience_intelligence import AudienceIntelligence

        stmt = select(AudienceIntelligence.content_profile_id).where(
            AudienceIntelligence.id == audience_intelligence_id
        )
        result = await self.session.execute(stmt)
        profile_id = result.scalar_one_or_none()
        if not profile_id:
            raise ValueError("Audience intelligence not found")
        return profile_id
