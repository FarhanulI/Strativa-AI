from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_draft import ContentDraft


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

    async def update(self, draft: ContentDraft) -> ContentDraft:
        await self.session.flush()
        return draft

    async def delete(self, draft: ContentDraft) -> bool:
        await self.session.delete(draft)
        await self.session.flush()
        return True
