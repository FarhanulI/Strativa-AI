import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.config import settings
from app.core.database import get_db_session
from app.infrastructure.redis_client import get_redis
from app.models.workspace_member import WorkspaceMember
from app.schemas.content_draft import ContentDraftResponse
from app.schemas.content_library import (
    ContentBriefLineageSummary,
    ContentLibraryItemResponse,
    ContentLibraryListResponse,
    ContentOpportunityLineageSummary,
)
from app.services.content_library import ContentLibraryService, InvalidCursorError

router = APIRouter(tags=["Content Library"])


async def get_content_library_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentLibraryService:
    return ContentLibraryService(session)


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def _default_view_cache_key(workspace_id: UUID, page_size: int) -> str:
    # workspace_id is part of the key (see app.api.v1.intelligence_analysis
    # for the same convention) so a cache hit can never cross a tenant
    # boundary; page_size is included since it's the only variable that can
    # still describe the "default" view.
    return f"workspace:{workspace_id}:library:default:page_size={page_size}"


@router.get("/library", response_model=ContentLibraryListResponse)
async def list_library_drafts(
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ContentLibraryService, Depends(get_content_library_service)],
    profile_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    platform: str | None = None,
    format: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    q: str | None = None,
    sort_by: str = "created_at",
    sort: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    cursor: str | None = None,
    page_size: int = Query(default=settings.content_library_default_page_size, ge=1),
) -> ContentLibraryListResponse:
    # Hard cap applied here too (not just in the service) so an oversized
    # page_size never disqualifies a request from being the cached default
    # view purely due to a value the service would have clamped anyway.
    page_size = min(page_size, settings.content_library_max_page_size)

    is_default_view = (
        profile_id is None
        and status_filter is None
        and platform is None
        and format is None
        and created_after is None
        and created_before is None
        and q is None
        and sort_by == "created_at"
        and sort == "desc"
        and cursor is None
        and page_size == settings.content_library_default_page_size
    )

    redis = get_redis()
    cache_key = _default_view_cache_key(workspace_member.workspace_id, page_size)
    if is_default_view:
        cached = await redis.get(cache_key)
        if cached is not None:
            return ContentLibraryListResponse(**json.loads(cached))

    try:
        page = await service.list_library(
            workspace_id=workspace_member.workspace_id,
            profile_id=profile_id,
            status=status_filter,
            platform=platform,
            format=format,
            created_after=created_after,
            created_before=created_before,
            search=q,
            sort_by=sort_by,
            sort_order=sort,
            cursor=cursor,
            page_size=page_size,
        )
    except InvalidCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        raise not_found(error) from error

    response = ContentLibraryListResponse(
        items=[ContentDraftResponse.model_validate(draft) for draft in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )

    if is_default_view:
        await redis.set(
            cache_key,
            json.dumps(jsonable_encoder(response)),
            ex=settings.library_default_view_cache_ttl_seconds,
        )

    return response


@router.get("/library/{draft_id}", response_model=ContentLibraryItemResponse)
async def get_library_draft(
    draft_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ContentLibraryService, Depends(get_content_library_service)],
) -> ContentLibraryItemResponse:
    try:
        draft = await service.get_library_item(draft_id, workspace_member.workspace_id)
    except ValueError as error:
        raise not_found(error) from error

    brief = draft.brief
    opportunity = brief.opportunity
    return ContentLibraryItemResponse(
        draft=ContentDraftResponse.model_validate(draft),
        brief=ContentBriefLineageSummary.model_validate(brief),
        opportunity=ContentOpportunityLineageSummary.model_validate(opportunity),
    )
