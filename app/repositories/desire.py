from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import Desire


class DesireRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, desire: Desire) -> Desire:
        self.session.add(desire)
        await self.session.flush()
        return desire

    async def get_by_id(self, desire_id: UUID) -> Desire | None:
        stmt = select(Desire).where(Desire.id == desire_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_audience(
        self, audience_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Desire]:
        stmt = (
            select(Desire)
            .where(Desire.audience_intelligence_id == audience_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, desire: Desire) -> Desire:
        await self.session.merge(desire)
        await self.session.flush()
        return desire

    async def delete(self, desire_id: UUID) -> bool:
        stmt = select(Desire).where(Desire.id == desire_id)
        result = await self.session.execute(stmt)
        desire = result.scalar_one_or_none()
        if not desire:
            return False
        await self.session.delete(desire)
        await self.session.flush()
        return True
