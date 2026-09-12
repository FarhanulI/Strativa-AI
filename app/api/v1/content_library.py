from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.content_draft import ContentDraftResponse
from app.schemas.content_library import (
    ContentBriefLineageSummary,
    ContentLibraryItemResponse,
    ContentOpportunityLineageSummary,
)
from app.services.content_library import ContentLibraryService

router = APIRouter(tags=["Content Library"])


async def get_content_library_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentLibraryService:
    return ContentLibraryService(session)


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("/library", response_model=list[ContentDraftResponse])
async def list_library_drafts(
    workspace_id: Annotated[UUID, Query(...)],
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
    skip: int = 0,
    limit: int = 100,
) -> list[ContentDraftResponse]:
    try:
        drafts = await service.list_library(
            workspace_id=workspace_id,
            profile_id=profile_id,
            status=status_filter,
            platform=platform,
            format=format,
            created_after=created_after,
            created_before=created_before,
            search=q,
            sort_by=sort_by,
            sort_order=sort,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise not_found(error) from error
    return [ContentDraftResponse.model_validate(draft) for draft in drafts]


@router.get("/library/{draft_id}", response_model=ContentLibraryItemResponse)
async def get_library_draft(
    draft_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentLibraryService, Depends(get_content_library_service)],
) -> ContentLibraryItemResponse:
    try:
        draft = await service.get_library_item(draft_id, workspace_id)
    except ValueError as error:
        raise not_found(error) from error

    brief = draft.brief
    opportunity = brief.opportunity
    return ContentLibraryItemResponse(
        draft=ContentDraftResponse.model_validate(draft),
        brief=ContentBriefLineageSummary.model_validate(brief),
        opportunity=ContentOpportunityLineageSummary.model_validate(opportunity),
    )
