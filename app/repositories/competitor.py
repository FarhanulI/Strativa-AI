from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor


class CompetitorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, competitor: Competitor) -> Competitor:
        self.session.add(competitor)
        await self.session.flush()
        return competitor

    async def get_by_id(self, competitor_id: UUID) -> Competitor | None:
        stmt = select(Competitor).where(Competitor.id == competitor_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_market(
        self, market_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Competitor]:
        stmt = (
            select(Competitor)
            .where(Competitor.market_intelligence_id == market_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, competitor: Competitor) -> Competitor:
        await self.session.merge(competitor)
        await self.session.flush()
        return competitor

    async def delete(self, competitor_id: UUID) -> bool:
        stmt = select(Competitor).where(Competitor.id == competitor_id)
        result = await self.session.execute(stmt)
        competitor = result.scalar_one_or_none()
        if not competitor:
            return False
        await self.session.delete(competitor)
        await self.session.flush()
        return True
