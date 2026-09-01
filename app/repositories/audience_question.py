from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceQuestion


class AudienceQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, question: AudienceQuestion) -> AudienceQuestion:
        self.session.add(question)
        await self.session.flush()
        return question

    async def get_by_id(self, question_id: UUID) -> AudienceQuestion | None:
        stmt = select(AudienceQuestion).where(AudienceQuestion.id == question_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_audience(
        self, audience_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[AudienceQuestion]:
        stmt = (
            select(AudienceQuestion)
            .where(AudienceQuestion.audience_intelligence_id == audience_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, question: AudienceQuestion) -> AudienceQuestion:
        await self.session.merge(question)
        await self.session.flush()
        return question

    async def delete(self, question_id: UUID) -> bool:
        stmt = select(AudienceQuestion).where(AudienceQuestion.id == question_id)
        result = await self.session.execute(stmt)
        question = result.scalar_one_or_none()
        if not question:
            return False
        await self.session.delete(question)
        await self.session.flush()
        return True
