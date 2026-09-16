import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.cache.service import CacheService
from app.infrastructure.redis_client import get_redis
from app.models.content_draft import ContentDraft
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.workspace import WorkspaceRepository

_SORT_FIELDS = ("created_at", "updated_at")
_SORT_ORDERS = ("asc", "desc")


class InvalidCursorError(ValueError):
    """Raised for a malformed cursor or one whose sort_by/sort_order no
    longer matches the request -- distinct from an ownership ValueError so
    the router can return 400 rather than 404.
    """


def library_cache_prefix(workspace_id: UUID) -> str:
    return f"workspace:{workspace_id}:library:"


async def invalidate_library_cache(workspace_id: UUID) -> None:
    """Drop every cached library read for a workspace. Called after any
    draft create/update (including a variation selection syncing into
    `ContentDraft.hook`/`caption`) so the cached default view never serves
    content that no longer matches the database.
    """
    await CacheService(get_redis()).invalidate_prefix(library_cache_prefix(workspace_id))


def encode_cursor(sort_by: str, sort_order: str, sort_key: datetime, item_id: UUID) -> str:
    payload = {
        "sort_by": sort_by,
        "sort_order": sort_order,
        "sort_key": sort_key.isoformat(),
        "id": str(item_id),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str, sort_by: str, sort_order: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
        cursor_sort_key = datetime.fromisoformat(payload["sort_key"])
        cursor_id = UUID(payload["id"])
        cursor_sort_by = payload["sort_by"]
        cursor_sort_order = payload["sort_order"]
    except Exception as error:
        raise InvalidCursorError("Invalid pagination cursor") from error
    if cursor_sort_by != sort_by or cursor_sort_order != sort_order:
        raise InvalidCursorError("Cursor does not match the requested sort_by/sort_order")
    return cursor_sort_key, cursor_id


@dataclass
class LibraryPage:
    items: list[ContentDraft]
    next_cursor: str | None
    has_more: bool


class ContentLibraryService:
    def __init__(self, session: AsyncSession):
        self.repository = ContentDraftRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.workspace_repository = WorkspaceRepository(session)

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
        cursor: str | None = None,
        page_size: int = settings.content_library_default_page_size,
    ) -> LibraryPage:
        await self._verify_workspace(workspace_id)
        if profile_id is not None:
            await self._verify_profile(profile_id, workspace_id)

        if sort_by not in _SORT_FIELDS:
            raise ValueError(f"Invalid sort_by: {sort_by}")
        if sort_order not in _SORT_ORDERS:
            raise ValueError(f"Invalid sort_order: {sort_order}")

        # Hard server-side cap regardless of what the client requested.
        page_size = max(1, min(page_size, settings.content_library_max_page_size))

        cursor_sort_key: datetime | None = None
        cursor_id: UUID | None = None
        if cursor is not None:
            cursor_sort_key, cursor_id = decode_cursor(cursor, sort_by, sort_order)

        rows = await self.repository.list_library_cursor(
            workspace_id=workspace_id,
            profile_id=profile_id,
            status=status,
            platform=platform,
            format=format,
            created_after=created_after,
            created_before=created_before,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            cursor_sort_key=cursor_sort_key,
            cursor_id=cursor_id,
            limit=page_size + 1,
        )
        has_more = len(rows) > page_size
        items = rows[:page_size]

        next_cursor = None
        if has_more and items:
            last = items[-1]
            sort_value = last.created_at if sort_by == "created_at" else last.updated_at
            next_cursor = encode_cursor(sort_by, sort_order, sort_value, last.id)

        return LibraryPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def get_library_item(self, draft_id: UUID, workspace_id: UUID) -> ContentDraft:
        await self._verify_workspace(workspace_id)
        draft = await self.repository.get_with_lineage(draft_id, workspace_id)
        if not draft:
            raise ValueError("Content draft not found")
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
