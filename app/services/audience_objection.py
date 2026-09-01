from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence, AudienceObjection
from app.repositories.audience_intelligence import AudienceIntelligenceRepository
from app.repositories.audience_objection import AudienceObjectionRepository
from app.repositories.content_profile import ContentProfileRepository


class AudienceObjectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AudienceObjectionRepository(session)
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
    ) -> AudienceObjection:
        """
        Create an objection within audience intelligence.
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

        objection = AudienceObjection(
            audience_intelligence_id=audience_intelligence_id,
            title=title,
            description=description,
            evidence=evidence,
            severity=severity,
            frequency=frequency,
        )
        await self.repository.create(objection)
        await self.session.commit()
        return objection

    async def get(
        self, audience_intelligence_id: UUID, objection_id: UUID, workspace_id: UUID
    ) -> AudienceObjection | None:
        """
        Get a specific objection with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        objection = await self.repository.get_by_id(objection_id)
        if not objection or objection.audience_intelligence_id != audience_intelligence_id:
            return None

        return objection

    async def list(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AudienceObjection]:
        """
        List objections for audience intelligence with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        return await self.repository.list_by_audience(
            audience_intelligence_id, skip=skip, limit=limit
        )

    async def update(
        self,
        audience_intelligence_id: UUID,
        objection_id: UUID,
        workspace_id: UUID,
        title: str | None = None,
        description: str | None = None,
        evidence: str | None = None,
        severity: int | None = None,
        frequency: int | None = None,
    ) -> AudienceObjection | None:
        """
        Update an objection.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        objection = await self.repository.get_by_id(objection_id)
        if not objection or objection.audience_intelligence_id != audience_intelligence_id:
            return None

        if title is not None:
            objection.title = title
        if description is not None:
            objection.description = description
        if evidence is not None:
            objection.evidence = evidence
        if severity is not None:
            objection.severity = severity
        if frequency is not None:
            objection.frequency = frequency

        await self.repository.update(objection)
        await self.session.commit()
        return objection

    async def delete(
        self, audience_intelligence_id: UUID, objection_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Delete an objection.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        objection = await self.repository.get_by_id(objection_id)
        if not objection or objection.audience_intelligence_id != audience_intelligence_id:
            return False

        success = await self.repository.delete(objection_id)
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
