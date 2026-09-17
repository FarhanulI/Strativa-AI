from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.models.content_profile import ContentProfile
from app.schemas.content_brief import ContentBriefCreate, ContentBriefResponse, ContentBriefUpdate
from app.services.content_brief import ContentBriefService

router = APIRouter(tags=["Content Briefs"])


async def get_content_brief_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentBriefService:
    return ContentBriefService(session)


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
    response_model=ContentBriefResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_brief(
    opportunity_id: UUID,
    payload: ContentBriefCreate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentBriefService, Depends(get_content_brief_service)],
) -> ContentBriefResponse:
    if payload.opportunity_id != opportunity_id:
        raise HTTPException(status_code=404, detail="Content opportunity not found")
    try:
        values = payload.model_dump(exclude={"opportunity_id"})
        brief = await service.create(profile.id, profile.workspace_id, opportunity_id, **values)
    except ValueError as error:
        raise not_found(error) from error
    return ContentBriefResponse.model_validate(brief)


@router.get(
    "/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
    response_model=list[ContentBriefResponse],
)
async def list_opportunity_briefs(
    opportunity_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentBriefService, Depends(get_content_brief_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[ContentBriefResponse]:
    try:
        briefs = await service.list_by_opportunity(
            profile.id, opportunity_id, profile.workspace_id, skip=skip, limit=limit
        )
    except ValueError as error:
        raise not_found(error) from error
    return [ContentBriefResponse.model_validate(brief) for brief in briefs]


@router.get("/profiles/{profile_id}/briefs", response_model=list[ContentBriefResponse])
async def list_profile_briefs(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentBriefService, Depends(get_content_brief_service)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    generation_source: str | None = None,
    target_objective: str | None = None,
    recommended_format: str | None = None,
    recommended_platform: str | None = None,
    opportunity_id: UUID | None = None,
    sort_by: str = "created_at",
    sort: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    skip: int = 0,
    limit: int = 100,
) -> list[ContentBriefResponse]:
    try:
        briefs = await service.list(
            profile.id,
            profile.workspace_id,
            status=status_filter,
            generation_source=generation_source,
            target_objective=target_objective,
            recommended_format=recommended_format,
            recommended_platform=recommended_platform,
            opportunity_id=opportunity_id,
            sort_by=sort_by,
            sort_order=sort,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise not_found(error) from error
    return [ContentBriefResponse.model_validate(brief) for brief in briefs]


@router.get("/profiles/{profile_id}/briefs/{brief_id}", response_model=ContentBriefResponse)
async def get_brief(
    brief_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentBriefService, Depends(get_content_brief_service)],
) -> ContentBriefResponse:
    try:
        brief = await service.get(profile.id, brief_id, profile.workspace_id)
    except ValueError as error:
        raise not_found(error) from error
    if not brief:
        raise HTTPException(status_code=404, detail="Content brief not found")
    return ContentBriefResponse.model_validate(brief)


@router.patch("/profiles/{profile_id}/briefs/{brief_id}", response_model=ContentBriefResponse)
async def update_brief(
    brief_id: UUID,
    payload: ContentBriefUpdate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentBriefService, Depends(get_content_brief_service)],
) -> ContentBriefResponse:
    try:
        brief = await service.update(
            profile.id, brief_id, profile.workspace_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise not_found(error) from error
    if not brief:
        raise HTTPException(status_code=404, detail="Content brief not found")
    return ContentBriefResponse.model_validate(brief)


@router.delete("/profiles/{profile_id}/briefs/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brief(
    brief_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentBriefService, Depends(get_content_brief_service)],
) -> None:
    try:
        deleted = await service.delete(profile.id, brief_id, profile.workspace_id)
    except ValueError as error:
        raise not_found(error) from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Content brief not found")
