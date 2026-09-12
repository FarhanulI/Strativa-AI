from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.content_draft import ContentDraftResponse
from app.schemas.content_library import ContentBriefLineageSummary, ContentOpportunityLineageSummary
from app.schemas.published_content import (
    PublishedContentCreate,
    PublishedContentLineageResponse,
    PublishedContentResponse,
    PublishedContentScheduleCreate,
)
from app.services.published_content import (
    DraftNotEligibleError,
    InvalidScheduleError,
    PublishedContentService,
    ScheduleNotCancellableError,
)

router = APIRouter(tags=["Publishing"])


async def get_published_content_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublishedContentService:
    return PublishedContentService(session)


def error_response(error: ValueError) -> HTTPException:
    if isinstance(error, DraftNotEligibleError | ScheduleNotCancellableError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, InvalidScheduleError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/profiles/{profile_id}/drafts/{draft_id}/publish",
    response_model=PublishedContentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_draft(
    profile_id: UUID,
    draft_id: UUID,
    payload: PublishedContentCreate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[PublishedContentService, Depends(get_published_content_service)],
) -> PublishedContentResponse:
    try:
        published = await service.publish_draft(
            workspace_id, profile_id, draft_id, external_url=payload.external_url
        )
    except ValueError as error:
        raise error_response(error) from error
    return PublishedContentResponse.model_validate(published)


@router.post(
    "/profiles/{profile_id}/drafts/{draft_id}/schedule",
    response_model=PublishedContentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_draft(
    profile_id: UUID,
    draft_id: UUID,
    payload: PublishedContentScheduleCreate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[PublishedContentService, Depends(get_published_content_service)],
) -> PublishedContentResponse:
    try:
        scheduled = await service.schedule_draft(
            workspace_id,
            profile_id,
            draft_id,
            scheduled_at=payload.scheduled_at,
            external_url=payload.external_url,
        )
    except ValueError as error:
        raise error_response(error) from error
    return PublishedContentResponse.model_validate(scheduled)


@router.post(
    "/profiles/{profile_id}/published/{published_id}/cancel",
    response_model=PublishedContentResponse,
)
async def cancel_scheduled_publish(
    profile_id: UUID,
    published_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[PublishedContentService, Depends(get_published_content_service)],
) -> PublishedContentResponse:
    try:
        cancelled = await service.cancel_schedule(workspace_id, profile_id, published_id)
    except ValueError as error:
        raise error_response(error) from error
    return PublishedContentResponse.model_validate(cancelled)


@router.get(
    "/profiles/{profile_id}/published",
    response_model=list[PublishedContentResponse],
)
async def list_published_content(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[PublishedContentService, Depends(get_published_content_service)],
    platform: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[PublishedContentResponse]:
    try:
        items = await service.list_published(
            workspace_id,
            profile_id,
            platform=platform,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise error_response(error) from error
    return [PublishedContentResponse.model_validate(item) for item in items]


@router.get(
    "/profiles/{profile_id}/published/{published_id}",
    response_model=PublishedContentLineageResponse,
)
async def get_published_content(
    profile_id: UUID,
    published_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[PublishedContentService, Depends(get_published_content_service)],
) -> PublishedContentLineageResponse:
    try:
        published = await service.get_published_item(workspace_id, published_id)
    except ValueError as error:
        raise error_response(error) from error

    if published.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Published content not found")

    draft = published.draft
    brief = draft.brief
    opportunity = brief.opportunity
    return PublishedContentLineageResponse(
        published=PublishedContentResponse.model_validate(published),
        draft=ContentDraftResponse.model_validate(draft),
        brief=ContentBriefLineageSummary.model_validate(brief),
        opportunity=ContentOpportunityLineageSummary.model_validate(opportunity),
    )
