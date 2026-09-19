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

    async def claim_publishing(self, now: datetime) -> list[PublishedContent]:
        """Atomically flip due scheduled rows to `publishing` and return them.

        This single atomic `UPDATE ... WHERE status = 'scheduled' ...
        RETURNING` is the entire claim-then-call correctness guarantee: only
        one instance's UPDATE can match and flip a given row, so the same row
        is never claimed twice even under N concurrent worker instances. A
        Day 15 `DistributedLock` wrapped around the caller (see
        `app.services.publish_promotion`) is a performance optimization on
        top of this, not a substitute for it.

        The caller is responsible for actually calling the platform adapter
        for each claimed row and resolving it to `published`/`failed` --
        this method only performs the claim.
        """
        statement = (
            update(PublishedContent)
            .where(
                PublishedContent.status == PublishStatus.SCHEDULED,
                PublishedContent.scheduled_at <= now,
            )
            .values(status=PublishStatus.PUBLISHING)
            .returning(PublishedContent)
        )
        # See `reclaim_stuck_publishing` for why `synchronize_session=False`.
        result = await self.session.execute(
            statement,
            execution_options={"populate_existing": True, "synchronize_session": False},
        )
        await self.session.flush()
        return list(result.scalars().all())

    async def reclaim_stuck_publishing(self, before: datetime) -> list[PublishedContent]:
        """Atomically move rows stuck in `publishing` past a timeout to
        `failed`, for manual review.

        A row can only be stuck here if a worker crashed (or was killed)
        after claiming it but before finishing the adapter call --
        `promote_due` itself always resolves a claimed row to a terminal
        status in the same job run. Same atomic `UPDATE ... RETURNING`
        pattern as `claim_publishing`, so a concurrent recovery sweep from
        another instance can't double-process the same stuck row either.
        """
        statement = (
            update(PublishedContent)
            .where(
                PublishedContent.status == PublishStatus.PUBLISHING,
                PublishedContent.updated_at <= before,
            )
            .values(
                status=PublishStatus.FAILED,
                published_metadata={"failure_reason": "stuck_publishing_timeout"},
            )
            .returning(PublishedContent)
        )
        # `synchronize_session=False`: `populate_existing` already refreshes
        # matched rows straight from RETURNING, so there is nothing to gain
        # from also re-evaluating the WHERE clause in Python against
        # already-loaded objects -- and that Python-side evaluation is
        # exactly what breaks on SQLite, whose driver drops tzinfo from a
        # datetime on round-trip (a `publishing` row already loaded earlier
        # in this session, e.g. by `claim_publishing`, would have a
        # tz-naive `updated_at` compared against a tz-aware `before`).
        result = await self.session.execute(
            statement,
            execution_options={"populate_existing": True, "synchronize_session": False},
        )
        await self.session.flush()
        return list(result.scalars().all())

    async def update(self, published: PublishedContent) -> PublishedContent:
        await self.session.flush()
        return published
