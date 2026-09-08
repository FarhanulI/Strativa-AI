from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_performance import ContentPerformance


class ContentPerformanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, record: ContentPerformance) -> ContentPerformance:
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, profile_id: UUID, record_id: UUID) -> ContentPerformance | None:
        result = await self.session.execute(
            select(ContentPerformance).where(
                ContentPerformance.profile_id == profile_id, ContentPerformance.id == record_id
            )
        )
        return result.scalar_one_or_none()

    async def list(self, profile_id: UUID, **filters: object) -> list[ContentPerformance]:
        statement = select(ContentPerformance).where(ContentPerformance.profile_id == profile_id)
        for field in ("platform", "format", "topic"):
            value = filters.get(field)
            if value is not None:
                statement = statement.where(getattr(ContentPerformance, field) == value)
        result = await self.session.execute(
            statement.order_by(ContentPerformance.published_at.desc())
            .offset(int(filters.get("skip", 0)))
            .limit(int(filters.get("limit", 100)))
        )
        return list(result.scalars().all())

    async def all(self, profile_id: UUID) -> list[ContentPerformance]:
        result = await self.session.execute(
            select(ContentPerformance).where(ContentPerformance.profile_id == profile_id)
        )
        return list(result.scalars().all())

    async def delete(self, record: ContentPerformance) -> None:
        await self.session.delete(record)
        await self.session.flush()
