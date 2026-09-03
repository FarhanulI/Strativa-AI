from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_opportunity import ContentOpportunity


class ContentOpportunityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, opportunity: ContentOpportunity) -> ContentOpportunity:
        self.session.add(opportunity)
        await self.session.flush()
        return opportunity

    async def get_by_id(self, profile_id: UUID, opportunity_id: UUID) -> ContentOpportunity | None:
        result = await self.session.execute(
            select(ContentOpportunity).where(
                ContentOpportunity.id == opportunity_id,
                ContentOpportunity.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: UUID,
        status: str | None = None,
        source_signal: str | None = None,
        target_objective: str | None = None,
        priority: str | None = None,
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContentOpportunity]:
        statement = select(ContentOpportunity).where(ContentOpportunity.profile_id == profile_id)
        if status is not None:
            statement = statement.where(ContentOpportunity.status == status)
        if source_signal is not None:
            statement = statement.where(ContentOpportunity.source_signal == source_signal)
        if target_objective is not None:
            statement = statement.where(ContentOpportunity.target_objective == target_objective)
        if priority is not None:
            statement = statement.where(ContentOpportunity.priority == priority)
        order_column = (
            ContentOpportunity.opportunity_score.desc()
            if sort_order == "desc"
            else ContentOpportunity.opportunity_score.asc()
        )
        result = await self.session.execute(
            statement.order_by(order_column).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, opportunity: ContentOpportunity) -> ContentOpportunity:
        await self.session.flush()
        return opportunity

    async def delete(self, opportunity: ContentOpportunity) -> bool:
        await self.session.delete(opportunity)
        await self.session.flush()
        return True
