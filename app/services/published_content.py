import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.social import ManualPlatformAdapter
from app.models.content_draft import ContentDraft, DraftStatus
from app.models.published_content import PublishedContent, PublishMethod, PublishStatus
from app.platform_connections.adapters import get_adapter
from app.platform_connections.models import ConnectionStatus, SocialPlatform
from app.platform_connections.repository import PlatformConnectionRepository
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.published_content import PublishedContentRepository
from app.repositories.workspace import WorkspaceRepository

logger = logging.getLogger(__name__)

ELIGIBLE_DRAFT_STATUSES = (DraftStatus.READY, DraftStatus.APPROVED)

# Platforms with a real, connection-authenticated adapter (Day 23/24).
# Anything else (e.g. a draft's inherited "other" platform) keeps using the
# original manual/no-op publish path and never needs a PlatformConnection.
_CONNECTION_PLATFORMS = {member.value for member in SocialPlatform}


class DraftNotEligibleError(ValueError):
    """Raised when a draft's status does not allow publishing."""


class InvalidScheduleError(ValueError):
    """Raised when a requested scheduled_at time is not usable."""


class ScheduleNotCancellableError(ValueError):
    """Raised when a published item is not in a cancellable state."""


class PlatformNotConnectedError(ValueError):
    """Raised when scheduling to youtube/facebook/instagram without an
    active `PlatformConnection` for the profile.
    """


def _resolve_connected_platform(platform: str) -> SocialPlatform | None:
    """Map a draft's free-text `platform` string to a `SocialPlatform` with
    a real adapter, or `None` if it isn't one (e.g. "other") -- those keep
    using the manual/no-op publish path unchanged.
    """
    normalized = platform.lower()
    if normalized not in _CONNECTION_PLATFORMS:
        return None
    return SocialPlatform(normalized)


def _draft_payload(draft: ContentDraft) -> dict[str, Any]:
    return {
        "id": str(draft.id),
        "title": draft.title,
        "hook": draft.hook,
        "body": draft.body,
        "cta": draft.cta,
        "caption": draft.caption,
    }


class PublishedContentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PublishedContentRepository(session)
        self.draft_repository = ContentDraftRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.workspace_repository = WorkspaceRepository(session)
        self.connection_repository = PlatformConnectionRepository(session)

    # --- Immediate publish --------------------------------------------------

    async def publish_draft(
        self,
        workspace_id: UUID,
        profile_id: UUID,
        draft_id: UUID,
        external_url: str | None = None,
    ) -> PublishedContent:
        draft = await self._get_eligible_draft(workspace_id, profile_id, draft_id)
        social_platform = _resolve_connected_platform(draft.platform)

        if social_platform is None:
            adapter = ManualPlatformAdapter()
            result = await adapter.publish(draft={"id": str(draft.id)}, platform=draft.platform)
            published = PublishedContent(
                draft_id=draft.id,
                profile_id=profile_id,
                platform=draft.platform,
                external_url=external_url or result.get("external_url"),
                publish_method=PublishMethod.MANUAL,
                status=PublishStatus.PUBLISHED,
                published_at=datetime.now(UTC),
            )
            created = await self.repository.create(published)
            await self.session.commit()
            return created

        published = PublishedContent(
            draft_id=draft.id,
            profile_id=profile_id,
            platform=draft.platform,
            external_url=external_url,
            publish_method=PublishMethod.API,
            status=PublishStatus.FAILED,
        )
        await self._call_connected_adapter(
            published, social_platform=social_platform, profile_id=profile_id, draft=draft
        )
        created = await self.repository.create(published)
        await self.session.commit()
        return created

    async def _call_connected_adapter(
        self,
        published: PublishedContent,
        *,
        social_platform: SocialPlatform,
        profile_id: UUID,
        draft: ContentDraft,
    ) -> None:
        """Shared by immediate publish and scheduled promotion: re-verify
        the connection is `connected` right before calling the real
        Day 23 adapter, then resolve `published` to its terminal status in
        place. Never raises -- every failure mode (no connection, expired
        connection, missing media, a platform HTTP error) becomes
        `status=failed` with the reason recorded, per the architecture's
        durable-failure-state rule.
        """
        connection = await self.connection_repository.get_for_profile_platform(
            profile_id, social_platform
        )
        if connection is None or connection.status is not ConnectionStatus.CONNECTED:
            self._mark_failed(
                published, PlatformNotConnectedError(f"{draft.platform} is not connected")
            )
            return

        adapter = get_adapter(social_platform)
        try:
            result = await adapter.publish_content(
                connection=connection, draft=_draft_payload(draft)
            )
        except Exception as error:  # noqa: BLE001 - every failure mode resolves to `failed`
            self._mark_failed(published, error)
            return

        published.status = PublishStatus.PUBLISHED
        published.published_at = datetime.now(UTC)
        published.platform_post_id = result.platform_post_id
        if result.external_url and not published.external_url:
            published.external_url = result.external_url

    def _mark_failed(self, published: PublishedContent, error: Exception) -> None:
        published.status = PublishStatus.FAILED
        published.published_metadata = {
            **(published.published_metadata or {}),
            "failure_reason": type(error).__name__,
            "detail": str(error)[:300],
        }
        logger.warning(
            "published_content.publish_failed",
            extra={
                "draft_id": str(published.draft_id),
                "platform": published.platform,
                "error": type(error).__name__,
            },
        )

    # --- Scheduling -----------------------------------------------------

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

        social_platform = _resolve_connected_platform(draft.platform)
        if social_platform is not None:
            connection = await self.connection_repository.get_for_profile_platform(
                profile_id, social_platform
            )
            if connection is None or connection.status is not ConnectionStatus.CONNECTED:
                raise PlatformNotConnectedError(
                    f"{draft.platform} is not connected for this profile"
                )

        scheduled = PublishedContent(
            draft_id=draft.id,
            profile_id=profile_id,
            platform=draft.platform,
            external_url=external_url,
            publish_method=PublishMethod.API if social_platform else PublishMethod.MANUAL,
            status=PublishStatus.SCHEDULED,
            scheduled_at=scheduled_at,
            published_at=None,
        )
        created = await self.repository.create(scheduled)
        await self.session.commit()
        return created

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
        updated = await self.repository.update(published)
        await self.session.commit()
        return updated

    # --- Distributed scheduler: claim then call -----------------------------

    async def promote_due(self, now: datetime | None = None) -> list[PublishedContent]:
        """Promote scheduled publishes whose time has arrived.

        Two-phase claim-then-call, safe under N concurrent worker instances:

        1. Claim: `PublishedContentRepository.claim_publishing` atomically
           flips due `scheduled` rows to `publishing` in one `UPDATE ...
           RETURNING`. That single atomic statement is the entire
           correctness guarantee -- only one instance's UPDATE can match a
           given row, so it can never be claimed twice. A `DistributedLock`
           wrapped around the caller (see `app.services.publish_promotion`)
           is a performance optimization on top of this, not a substitute.
        2. Call: only after claiming, each row is resolved to a terminal
           status by actually calling the platform adapter (or the manual
           no-op path). There is deliberately no retry here -- retrying an
           uncertain external call risks a duplicate post.
        """
        current_time = now or datetime.now(UTC)
        claimed = await self.repository.claim_publishing(current_time)

        for item in claimed:
            await self._resolve_claimed_item(item, when=current_time)
        return claimed

    async def _resolve_claimed_item(self, item: PublishedContent, *, when: datetime) -> None:
        social_platform = _resolve_connected_platform(item.platform)

        if social_platform is None:
            adapter = ManualPlatformAdapter()
            try:
                result = await adapter.publish(
                    draft={"id": str(item.draft_id)}, platform=item.platform
                )
            except Exception as error:  # noqa: BLE001 - resolves to `failed`, no retry
                self._mark_failed(item, error)
            else:
                item.status = PublishStatus.PUBLISHED
                item.published_at = when
                if not item.external_url:
                    item.external_url = result.get("external_url")
            await self.repository.update(item)
            return

        draft = await self.draft_repository.get_by_id(item.profile_id, item.draft_id)
        if draft is None:
            self._mark_failed(item, ValueError("Source draft no longer exists"))
            await self.repository.update(item)
            return

        await self._call_connected_adapter(
            item, social_platform=social_platform, profile_id=item.profile_id, draft=draft
        )
        if item.status == PublishStatus.PUBLISHED:
            item.published_at = when
        await self.repository.update(item)

    # --- Recovery sweep -------------------------------------------------

    async def recover_stuck_publishing(self, now: datetime | None = None) -> list[PublishedContent]:
        """Move rows stuck in `publishing` past the configured timeout to
        `failed`, for manual review. A row is only ever stuck here if a
        worker died mid-call after claiming it -- `promote_due` always
        resolves a claimed row to a terminal status within the same tick.
        """
        current_time = now or datetime.now(UTC)
        before = current_time - timedelta(seconds=settings.publish_stuck_publishing_timeout_seconds)
        return await self.repository.reclaim_stuck_publishing(before)

    # --- Reads -----------------------------------------------------------

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

    # --- Ownership helpers -------------------------------------------------

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
