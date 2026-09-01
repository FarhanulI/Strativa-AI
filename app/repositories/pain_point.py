from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import PainPoint


class PainPointRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, pain_point: PainPoint) -> PainPoint:
        self.session.add(pain_point)
        await self.session.flush()
        return pain_point

    async def get_by_id(self, pain_point_id: UUID) -> PainPoint | None:
        stmt = select(PainPoint).where(PainPoint.id == pain_point_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_audience(
        self, audience_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[PainPoint]:
        stmt = (
            select(PainPoint)
            .where(PainPoint.audience_intelligence_id == audience_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, pain_point: PainPoint) -> PainPoint:
        await self.session.merge(pain_point)
        await self.session.flush()
        return pain_point

    async def delete(self, pain_point_id: UUID) -> bool:
        stmt = select(PainPoint).where(PainPoint.id == pain_point_id)
        result = await self.session.execute(stmt)
        pain_point = result.scalar_one_or_none()
        if not pain_point:
            return False
        await self.session.delete(pain_point)
        await self.session.flush()
        return True
