from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content_brief import ContentBrief
from app.models.content_draft import ContentDraft
from app.models.content_profile import ContentProfile
from app.models.published_content import PublishedContent, PublishStatus


class PublishedContentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, published: PublishedContent) -> PublishedContent:
        self.session.add(published)
        await self.session.flush()
        return published

    async def get_by_id(self, profile_id: UUID, published_id: UUID) -> PublishedContent | None:
        result = await self.session.execute(
            select(PublishedContent).where(
                PublishedContent.id == published_id,
                PublishedContent.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: UUID,
        platform: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PublishedContent]:
        statement = select(PublishedContent).where(PublishedContent.profile_id == profile_id)
        for column, value in (
            (PublishedContent.platform, platform),
            (PublishedContent.status, status),
        ):
            if value is not None:
                statement = statement.where(column == value)
        result = await self.session.execute(
            statement.order_by(PublishedContent.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_with_lineage(
        self, published_id: UUID, workspace_id: UUID
    ) -> PublishedContent | None:
        statement = (
            select(PublishedContent)
            .join(ContentProfile, ContentProfile.id == PublishedContent.profile_id)
            .where(
                PublishedContent.id == published_id,
                ContentProfile.workspace_id == workspace_id,
            )
            .options(
                selectinload(PublishedContent.draft)
                .selectinload(ContentDraft.brief)
                .selectinload(ContentBrief.opportunity)
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def claim_due(self, now: datetime) -> list[PublishedContent]:
        """Atomically flip due scheduled rows to published and return them.

        The `WHERE status = SCHEDULED` guard makes this safe to call from more
        than one app instance concurrently: only one instance's UPDATE can
        match and flip a given row, so the same row is never claimed twice.
        """
        statement = (
            update(PublishedContent)
            .where(
                PublishedContent.status == PublishStatus.SCHEDULED,
                PublishedContent.scheduled_at <= now,
            )
            .values(status=PublishStatus.PUBLISHED, published_at=now)
            .returning(PublishedContent)
        )
        result = await self.session.execute(
            statement, execution_options={"populate_existing": True}
        )
        await self.session.flush()
        return list(result.scalars().all())

    async def update(self, published: PublishedContent) -> PublishedContent:
        await self.session.flush()
        return published
