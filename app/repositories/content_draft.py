from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content_brief import ContentBrief
from app.models.content_draft import ContentDraft
from app.models.content_profile import ContentProfile


class ContentDraftRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, draft: ContentDraft) -> ContentDraft:
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def get_by_id(self, profile_id: UUID, draft_id: UUID) -> ContentDraft | None:
        result = await self.session.execute(
            select(ContentDraft).where(
                ContentDraft.id == draft_id, ContentDraft.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: UUID,
        status: str | None = None,
        platform: str | None = None,
        format: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContentDraft]:
        statement = select(ContentDraft).where(ContentDraft.profile_id == profile_id)
        for column, value in (
            (ContentDraft.status, status),
            (ContentDraft.platform, platform),
            (ContentDraft.format, format),
        ):
            if value is not None:
                statement = statement.where(column == value)
        result = await self.session.execute(
            statement.order_by(ContentDraft.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def list_library(
        self,
        workspace_id: UUID,
        profile_id: UUID | None = None,
        status: str | None = None,
        platform: str | None = None,
        format: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContentDraft]:
        statement = (
            select(ContentDraft)
            .join(ContentProfile, ContentProfile.id == ContentDraft.profile_id)
            .where(ContentProfile.workspace_id == workspace_id)
        )
        for column, value in (
            (ContentDraft.profile_id, profile_id),
            (ContentDraft.status, status),
            (ContentDraft.platform, platform),
            (ContentDraft.format, format),
        ):
            if value is not None:
                statement = statement.where(column == value)
        if created_after is not None:
            statement = statement.where(ContentDraft.created_at >= created_after)
        if created_before is not None:
            statement = statement.where(ContentDraft.created_at <= created_before)
        if search is not None and search.strip():
            query = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    ContentDraft.title.ilike(query),
                    ContentDraft.hook.ilike(query),
                    ContentDraft.caption.ilike(query),
                )
            )
        sort_column = {
            "created_at": ContentDraft.created_at,
            "updated_at": ContentDraft.updated_at,
        }.get(sort_by, ContentDraft.created_at)
        order_by = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        result = await self.session.execute(statement.order_by(order_by).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_with_lineage(self, draft_id: UUID, workspace_id: UUID) -> ContentDraft | None:
        statement = (
            select(ContentDraft)
            .join(ContentProfile, ContentProfile.id == ContentDraft.profile_id)
            .where(ContentDraft.id == draft_id, ContentProfile.workspace_id == workspace_id)
            .options(selectinload(ContentDraft.brief).selectinload(ContentBrief.opportunity))
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(self, draft: ContentDraft) -> ContentDraft:
        await self.session.flush()
        return draft

    async def delete(self, draft: ContentDraft) -> bool:
        await self.session.delete(draft)
        await self.session.flush()
        return True
