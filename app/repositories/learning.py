from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import Learning, LearningDimension, LearningStatus


class LearningRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, learning: Learning) -> Learning:
        self.session.add(learning)
        await self.session.flush()
        return learning

    async def get_by_id(self, profile_id: UUID, learning_id: UUID) -> Learning | None:
        result = await self.session.execute(
            select(Learning).where(Learning.id == learning_id, Learning.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_by_pattern(
        self, profile_id: UUID, dimension: LearningDimension, dimension_value: str
    ) -> Learning | None:
        result = await self.session.execute(
            select(Learning).where(
                Learning.profile_id == profile_id,
                Learning.dimension == dimension,
                Learning.dimension_value == dimension_value,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: UUID,
        status: str | None = None,
        dimension: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Learning]:
        statement = select(Learning).where(Learning.profile_id == profile_id)
        if status is not None:
            statement = statement.where(Learning.status == status)
        if dimension is not None:
            statement = statement.where(Learning.dimension == dimension)
        result = await self.session.execute(
            statement.order_by(Learning.confidence_level.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def list_active_for_dimensions(
        self, profile_id: UUID, dimensions: Sequence[LearningDimension]
    ) -> list[Learning]:
        """The scorer's per-opportunity read (app/ai/strategy/
        opportunity_scorer.py) -- a single query against the
        `(profile_id, status, dimension)` index, not a scan.
        """
        result = await self.session.execute(
            select(Learning).where(
                Learning.profile_id == profile_id,
                Learning.status == LearningStatus.ACTIVE,
                Learning.dimension.in_(dimensions),
            )
        )
        return list(result.scalars().all())

    async def update(self, learning: Learning) -> Learning:
        await self.session.flush()
        return learning

    async def delete(self, learning: Learning) -> None:
        await self.session.delete(learning)
        await self.session.flush()
