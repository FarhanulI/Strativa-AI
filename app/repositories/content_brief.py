from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_brief import ContentBrief


class ContentBriefRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, brief: ContentBrief) -> ContentBrief:
        self.session.add(brief)
        await self.session.flush()
        return brief

    async def get_by_id(self, profile_id: UUID, brief_id: UUID) -> ContentBrief | None:
        result = await self.session.execute(
            select(ContentBrief).where(
                ContentBrief.id == brief_id, ContentBrief.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_opportunity(
        self, profile_id: UUID, opportunity_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ContentBrief]:
        result = await self.session.execute(
            select(ContentBrief)
            .where(
                ContentBrief.profile_id == profile_id,
                ContentBrief.opportunity_id == opportunity_id,
            )
            .order_by(ContentBrief.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_profile(
        self,
        profile_id: UUID,
        status: str | None = None,
        generation_source: str | None = None,
        target_objective: str | None = None,
        recommended_format: str | None = None,
        recommended_platform: str | None = None,
        opportunity_id: UUID | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContentBrief]:
        statement = select(ContentBrief).where(ContentBrief.profile_id == profile_id)
        filters = (
            (ContentBrief.status, status),
            (ContentBrief.generation_source, generation_source),
            (ContentBrief.target_objective, target_objective),
            (ContentBrief.recommended_format, recommended_format),
            (ContentBrief.recommended_platform, recommended_platform),
            (ContentBrief.opportunity_id, opportunity_id),
        )
        for column, value in filters:
            if value is not None:
                statement = statement.where(column == value)
        order_column = getattr(ContentBrief, sort_by, ContentBrief.created_at)
        statement = statement.order_by(
            order_column.desc() if sort_order == "desc" else order_column.asc()
        )
        result = await self.session.execute(statement.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(self, brief: ContentBrief) -> ContentBrief:
        await self.session.flush()
        return brief

    async def delete(self, brief: ContentBrief) -> bool:
        await self.session.delete(brief)
        await self.session.flush()
        return True
