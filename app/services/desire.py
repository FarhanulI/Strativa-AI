from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence, Desire
from app.repositories.audience_intelligence import AudienceIntelligenceRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.desire import DesireRepository


class DesireService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = DesireRepository(session)
        self.audience_repository = AudienceIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        title: str,
        description: str | None = None,
        evidence: str | None = None,
        importance: int | None = None,
    ) -> Desire:
        """
        Create a desire within audience intelligence.
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

        desire = Desire(
            audience_intelligence_id=audience_intelligence_id,
            title=title,
            description=description,
            evidence=evidence,
            importance=importance,
        )
        await self.repository.create(desire)
        await self.session.commit()
        return desire

    async def get(
        self, audience_intelligence_id: UUID, desire_id: UUID, workspace_id: UUID
    ) -> Desire | None:
        """
        Get a specific desire with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        desire = await self.repository.get_by_id(desire_id)
        if not desire or desire.audience_intelligence_id != audience_intelligence_id:
            return None

        return desire

    async def list(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Desire]:
        """
        List desires for audience intelligence with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        return await self.repository.list_by_audience(
            audience_intelligence_id, skip=skip, limit=limit
        )

    async def update(
        self,
        audience_intelligence_id: UUID,
        desire_id: UUID,
        workspace_id: UUID,
        title: str | None = None,
        description: str | None = None,
        evidence: str | None = None,
        importance: int | None = None,
    ) -> Desire | None:
        """
        Update a desire.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        desire = await self.repository.get_by_id(desire_id)
        if not desire or desire.audience_intelligence_id != audience_intelligence_id:
            return None

        if title is not None:
            desire.title = title
        if description is not None:
            desire.description = description
        if evidence is not None:
            desire.evidence = evidence
        if importance is not None:
            desire.importance = importance

        await self.repository.update(desire)
        await self.session.commit()
        return desire

    async def delete(
        self, audience_intelligence_id: UUID, desire_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Delete a desire.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        desire = await self.repository.get_by_id(desire_id)
        if not desire or desire.audience_intelligence_id != audience_intelligence_id:
            return False

        success = await self.repository.delete(desire_id)
        if success:
            await self.session.commit()
        return success

    async def _verify_workspace_access(
        self, audience_intelligence_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Verify that audience intelligence belongs to the workspace.
        """
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
        """
        stmt = select(AudienceIntelligence.content_profile_id).where(
            AudienceIntelligence.id == audience_intelligence_id
        )
        result = await self.session.execute(stmt)
        profile_id = result.scalar_one_or_none()
        if not profile_id:
            raise ValueError("Audience intelligence not found")
        return profile_id
