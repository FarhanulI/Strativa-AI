from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_signal import MarketSignal


class MarketSignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal: MarketSignal) -> MarketSignal:
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def get_by_id(self, signal_id: UUID) -> MarketSignal | None:
        stmt = select(MarketSignal).where(MarketSignal.id == signal_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_market(
        self,
        market_intelligence_id: UUID,
        status: str | None = None,
        signal_type: str | None = None,
        topic_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MarketSignal]:
        stmt = select(MarketSignal).where(
            MarketSignal.market_intelligence_id == market_intelligence_id
        )
        if status is not None:
            stmt = stmt.where(MarketSignal.status == status)
        if signal_type is not None:
            stmt = stmt.where(MarketSignal.signal_type == signal_type)
        if topic_id is not None:
            stmt = stmt.where(MarketSignal.topic_id == topic_id)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, signal: MarketSignal) -> MarketSignal:
        await self.session.merge(signal)
        await self.session.flush()
        return signal

    async def delete(self, signal_id: UUID) -> bool:
        stmt = select(MarketSignal).where(MarketSignal.id == signal_id)
        result = await self.session.execute(stmt)
        signal = result.scalar_one_or_none()
        if not signal:
            return False
        await self.session.delete(signal)
        await self.session.flush()
        return True
