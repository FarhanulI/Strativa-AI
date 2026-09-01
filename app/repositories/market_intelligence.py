from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_intelligence import MarketIntelligence


class MarketIntelligenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, market_intelligence: MarketIntelligence) -> MarketIntelligence:
        self.session.add(market_intelligence)
        await self.session.flush()
        return market_intelligence

    async def get_by_profile(self, content_profile_id: UUID) -> MarketIntelligence | None:
        stmt = select(MarketIntelligence).where(
            MarketIntelligence.content_profile_id == content_profile_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, market_intelligence_id: UUID) -> MarketIntelligence | None:
        stmt = select(MarketIntelligence).where(MarketIntelligence.id == market_intelligence_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, market_intelligence: MarketIntelligence) -> MarketIntelligence:
        await self.session.merge(market_intelligence)
        await self.session.flush()
        return market_intelligence

    async def delete(self, market_intelligence_id: UUID) -> bool:
        stmt = select(MarketIntelligence).where(MarketIntelligence.id == market_intelligence_id)
        result = await self.session.execute(stmt)
        market_intelligence = result.scalar_one_or_none()
        if not market_intelligence:
            return False
        await self.session.delete(market_intelligence)
        await self.session.flush()
        return True
