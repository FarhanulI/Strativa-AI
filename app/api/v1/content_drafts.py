from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.content_draft import ContentDraftCreate, ContentDraftResponse, ContentDraftUpdate
from app.services.content_creation.service import ContentCreationService

router = APIRouter(tags=["Content Drafts"])


async def get_content_creation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentCreationService:
    return ContentCreationService(session)


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/profiles/{profile_id}/briefs/{brief_id}/drafts",
    response_model=ContentDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    profile_id: UUID,
    brief_id: UUID,
    payload: ContentDraftCreate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentCreationService, Depends(get_content_creation_service)],
) -> ContentDraftResponse:
    try:
        draft = await service.create(profile_id, brief_id, workspace_id, **payload.model_dump())
    except ValueError as error:
        raise not_found(error) from error
    return ContentDraftResponse.model_validate(draft)


@router.get("/profiles/{profile_id}/drafts", response_model=list[ContentDraftResponse])
async def list_drafts(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentCreationService, Depends(get_content_creation_service)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    platform: str | None = None,
    format: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[ContentDraftResponse]:
    try:
        drafts = await service.list(
            profile_id,
            workspace_id,
            status=status_filter,
            platform=platform,
            format=format,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise not_found(error) from error
    return [ContentDraftResponse.model_validate(draft) for draft in drafts]


@router.get("/profiles/{profile_id}/drafts/{draft_id}", response_model=ContentDraftResponse)
async def get_draft(
    profile_id: UUID,
    draft_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentCreationService, Depends(get_content_creation_service)],
) -> ContentDraftResponse:
    try:
        draft = await service.get(profile_id, draft_id, workspace_id)
    except ValueError as error:
        raise not_found(error) from error
    if not draft:
        raise HTTPException(status_code=404, detail="Content draft not found")
    return ContentDraftResponse.model_validate(draft)


@router.patch("/profiles/{profile_id}/drafts/{draft_id}", response_model=ContentDraftResponse)
async def update_draft(
    profile_id: UUID,
    draft_id: UUID,
    payload: ContentDraftUpdate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentCreationService, Depends(get_content_creation_service)],
) -> ContentDraftResponse:
    try:
        draft = await service.update(
            profile_id, draft_id, workspace_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise not_found(error) from error
    if not draft:
        raise HTTPException(status_code=404, detail="Content draft not found")
    return ContentDraftResponse.model_validate(draft)


@router.delete("/profiles/{profile_id}/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    profile_id: UUID,
    draft_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentCreationService, Depends(get_content_creation_service)],
) -> None:
    try:
        deleted = await service.delete(profile_id, draft_id, workspace_id)
    except ValueError as error:
        raise not_found(error) from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Content draft not found")
