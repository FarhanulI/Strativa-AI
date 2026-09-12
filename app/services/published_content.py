from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.social import ManualPlatformAdapter
from app.models.content_draft import ContentDraft, DraftStatus
from app.models.published_content import PublishedContent, PublishMethod, PublishStatus
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.published_content import PublishedContentRepository
from app.repositories.workspace import WorkspaceRepository

ELIGIBLE_DRAFT_STATUSES = (DraftStatus.READY, DraftStatus.APPROVED)


class DraftNotEligibleError(ValueError):
    """Raised when a draft's status does not allow publishing."""


class InvalidScheduleError(ValueError):
    """Raised when a requested scheduled_at time is not usable."""


class ScheduleNotCancellableError(ValueError):
    """Raised when a published item is not in a cancellable state."""


class PublishedContentService:
    def __init__(self, session: AsyncSession):
        self.repository = PublishedContentRepository(session)
        self.draft_repository = ContentDraftRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.workspace_repository = WorkspaceRepository(session)

    async def publish_draft(
        self,
        workspace_id: UUID,
        profile_id: UUID,
        draft_id: UUID,
        external_url: str | None = None,
    ) -> PublishedContent:
        draft = await self._get_eligible_draft(workspace_id, profile_id, draft_id)

        adapter = ManualPlatformAdapter()
        await adapter.publish(draft={"id": str(draft.id)}, platform=draft.platform)

        published = PublishedContent(
            draft_id=draft.id,
            profile_id=profile_id,
            platform=draft.platform,
            external_url=external_url,
            publish_method=PublishMethod.MANUAL,
            status=PublishStatus.PUBLISHED,
            published_at=datetime.now(UTC),
        )
        return await self.repository.create(published)

    async def schedule_draft(
        self,
        workspace_id: UUID,
        profile_id: UUID,
        draft_id: UUID,
        scheduled_at: datetime,
        external_url: str | None = None,
    ) -> PublishedContent:
        draft = await self._get_eligible_draft(workspace_id, profile_id, draft_id)

        if scheduled_at <= datetime.now(UTC):
            raise InvalidScheduleError("scheduled_at must be in the future")

        scheduled = PublishedContent(
            draft_id=draft.id,
            profile_id=profile_id,
            platform=draft.platform,
            external_url=external_url,
            publish_method=PublishMethod.MANUAL,
            status=PublishStatus.SCHEDULED,
            scheduled_at=scheduled_at,
            published_at=None,
        )
        return await self.repository.create(scheduled)

    async def cancel_schedule(
        self, workspace_id: UUID, profile_id: UUID, published_id: UUID
    ) -> PublishedContent:
        await self._verify_profile(profile_id, workspace_id)

        published = await self.repository.get_by_id(profile_id, published_id)
        if not published:
            raise ValueError("Published content not found")

        if published.status != PublishStatus.SCHEDULED:
            raise ScheduleNotCancellableError("Only a scheduled publish can be cancelled")

        published.status = PublishStatus.CANCELLED
        return await self.repository.update(published)

    async def promote_due(self, now: datetime | None = None) -> list[PublishedContent]:
        """Promote scheduled publishes whose time has arrived.

        This is the single operation the in-process publish scheduler calls on
        each tick. The atomic claim in the repository guards against
        double-processing if this ever runs from more than one app instance.
        It does not retry failed platform calls and does not implement a
        general job queue — only manual/no-op publishing exists today (see
        app.integrations.social.ManualPlatformAdapter).
        """
        current_time = now or datetime.now(UTC)
        claimed = await self.repository.claim_due(current_time)

        adapter = ManualPlatformAdapter()
        for item in claimed:
            await adapter.publish(draft={"id": str(item.draft_id)}, platform=item.platform)
        return claimed

    async def list_published(
        self,
        workspace_id: UUID,
        profile_id: UUID,
        platform: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PublishedContent]:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.list_by_profile(
            profile_id=profile_id, platform=platform, status=status, skip=skip, limit=limit
        )

    async def get_published_item(self, workspace_id: UUID, published_id: UUID) -> PublishedContent:
        await self._verify_workspace(workspace_id)
        published = await self.repository.get_with_lineage(published_id, workspace_id)
        if not published:
            raise ValueError("Published content not found")
        return published

    async def _get_eligible_draft(
        self, workspace_id: UUID, profile_id: UUID, draft_id: UUID
    ) -> ContentDraft:
        await self._verify_profile(profile_id, workspace_id)

        draft = await self.draft_repository.get_by_id(profile_id, draft_id)
        if not draft:
            raise ValueError("Content draft not found")

        if draft.status not in ELIGIBLE_DRAFT_STATUSES:
            raise DraftNotEligibleError("Draft is not eligible for publishing")

        return draft

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    async def _verify_workspace(self, workspace_id: UUID):
        workspace = await self.workspace_repository.get_by_id(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        return workspace
