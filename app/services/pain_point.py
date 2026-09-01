from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence, PainPoint
from app.repositories.audience_intelligence import AudienceIntelligenceRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.pain_point import PainPointRepository


class PainPointService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PainPointRepository(session)
        self.audience_repository = AudienceIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        title: str,
        description: str | None = None,
        evidence: str | None = None,
        severity: int | None = None,
        frequency: int | None = None,
    ) -> PainPoint:
        """
        Create a pain point within audience intelligence.
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

        pain_point = PainPoint(
            audience_intelligence_id=audience_intelligence_id,
            title=title,
            description=description,
            evidence=evidence,
            severity=severity,
            frequency=frequency,
        )
        await self.repository.create(pain_point)
        await self.session.commit()
        return pain_point

    async def get(
        self, audience_intelligence_id: UUID, pain_point_id: UUID, workspace_id: UUID
    ) -> PainPoint | None:
        """
        Get a specific pain point with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        pain_point = await self.repository.get_by_id(pain_point_id)
        if not pain_point or pain_point.audience_intelligence_id != audience_intelligence_id:
            return None

        return pain_point

    async def list(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PainPoint]:
        """
        List pain points for audience intelligence with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        return await self.repository.list_by_audience(
            audience_intelligence_id, skip=skip, limit=limit
        )

    async def update(
        self,
        audience_intelligence_id: UUID,
        pain_point_id: UUID,
        workspace_id: UUID,
        title: str | None = None,
        description: str | None = None,
        evidence: str | None = None,
        severity: int | None = None,
        frequency: int | None = None,
    ) -> PainPoint | None:
        """
        Update a pain point.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        pain_point = await self.repository.get_by_id(pain_point_id)
        if not pain_point or pain_point.audience_intelligence_id != audience_intelligence_id:
            return None

        if title is not None:
            pain_point.title = title
        if description is not None:
            pain_point.description = description
        if evidence is not None:
            pain_point.evidence = evidence
        if severity is not None:
            pain_point.severity = severity
        if frequency is not None:
            pain_point.frequency = frequency

        await self.repository.update(pain_point)
        await self.session.commit()
        return pain_point

    async def delete(
        self, audience_intelligence_id: UUID, pain_point_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Delete a pain point.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        pain_point = await self.repository.get_by_id(pain_point_id)
        if not pain_point or pain_point.audience_intelligence_id != audience_intelligence_id:
            return False

        success = await self.repository.delete(pain_point_id)
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
