from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence, AudienceQuestion
from app.repositories.audience_intelligence import AudienceIntelligenceRepository
from app.repositories.audience_question import AudienceQuestionRepository
from app.repositories.content_profile import ContentProfileRepository


class AudienceQuestionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AudienceQuestionRepository(session)
        self.audience_repository = AudienceIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        question: str,
        context: str | None = None,
        evidence: str | None = None,
        frequency: int | None = None,
        importance: int | None = None,
    ) -> AudienceQuestion:
        """
        Create a question within audience intelligence.
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

        question_obj = AudienceQuestion(
            audience_intelligence_id=audience_intelligence_id,
            question=question,
            context=context,
            evidence=evidence,
            frequency=frequency,
            importance=importance,
        )
        await self.repository.create(question_obj)
        await self.session.commit()
        return question_obj

    async def get(
        self, audience_intelligence_id: UUID, question_id: UUID, workspace_id: UUID
    ) -> AudienceQuestion | None:
        """
        Get a specific question with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        question_obj = await self.repository.get_by_id(question_id)
        if not question_obj or question_obj.audience_intelligence_id != audience_intelligence_id:
            return None

        return question_obj

    async def list(
        self,
        audience_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AudienceQuestion]:
        """
        List questions for audience intelligence with workspace verification.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        return await self.repository.list_by_audience(
            audience_intelligence_id, skip=skip, limit=limit
        )

    async def update(
        self,
        audience_intelligence_id: UUID,
        question_id: UUID,
        workspace_id: UUID,
        question: str | None = None,
        context: str | None = None,
        evidence: str | None = None,
        frequency: int | None = None,
        importance: int | None = None,
    ) -> AudienceQuestion | None:
        """
        Update a question.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        question_obj = await self.repository.get_by_id(question_id)
        if (
            not question_obj
            or question_obj.audience_intelligence_id != audience_intelligence_id
        ):
            return None

        if question is not None:
            question_obj.question = question
        if context is not None:
            question_obj.context = context
        if evidence is not None:
            question_obj.evidence = evidence
        if frequency is not None:
            question_obj.frequency = frequency
        if importance is not None:
            question_obj.importance = importance

        await self.repository.update(question_obj)
        await self.session.commit()
        return question_obj

    async def delete(
        self, audience_intelligence_id: UUID, question_id: UUID, workspace_id: UUID
    ) -> bool:
        """
        Delete a question.
        """
        await self._verify_workspace_access(audience_intelligence_id, workspace_id)

        question_obj = await self.repository.get_by_id(question_id)
        if (
            not question_obj
            or question_obj.audience_intelligence_id != audience_intelligence_id
        ):
            return False

        success = await self.repository.delete(question_id)
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
