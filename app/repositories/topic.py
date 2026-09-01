from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic


class TopicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, topic: Topic) -> Topic:
        self.session.add(topic)
        await self.session.flush()
        return topic

    async def get_by_id(self, topic_id: UUID) -> Topic | None:
        stmt = select(Topic).where(Topic.id == topic_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, market_intelligence_id: UUID, name: str) -> Topic | None:
        stmt = select(Topic).where(
            (Topic.market_intelligence_id == market_intelligence_id) & (Topic.name == name)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_market(
        self, market_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Topic]:
        stmt = (
            select(Topic)
            .where(Topic.market_intelligence_id == market_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, topic: Topic) -> Topic:
        await self.session.merge(topic)
        await self.session.flush()
        return topic

    async def delete(self, topic_id: UUID) -> bool:
        stmt = select(Topic).where(Topic.id == topic_id)
        result = await self.session.execute(stmt)
        topic = result.scalar_one_or_none()
        if not topic:
            return False
        await self.session.delete(topic)
        await self.session.flush()
        return True
