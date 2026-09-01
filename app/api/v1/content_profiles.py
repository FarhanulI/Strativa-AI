from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.content_profile import (
    ContentProfileCreate,
    ContentProfileResponse,
    ContentProfileUpdate,
)
from app.services.content_profile import ContentProfileService

router = APIRouter(prefix="/profiles", tags=["Content Profiles"])


async def get_content_profile_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentProfileService:
    return ContentProfileService(session)


@router.post("", response_model=ContentProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_content_profile(
    payload: ContentProfileCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ContentProfileService, Depends(get_content_profile_service)],
) -> ContentProfileResponse:
    profile = await service.create(
        workspace_id=workspace_id,
        type=payload.type,
        name=payload.name,
        description=payload.description,
        website=payload.website,
        location=payload.location,
        positioning=payload.positioning,
        topics=payload.topics,
        expertise=payload.expertise,
        goals=payload.goals,
    )
    return ContentProfileResponse.model_validate(profile)


@router.get("", response_model=list[ContentProfileResponse])
async def list_content_profiles(
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ContentProfileService, Depends(get_content_profile_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[ContentProfileResponse]:
    profiles = await service.list(workspace_id=workspace_id, skip=skip, limit=limit)
    return [ContentProfileResponse.model_validate(profile) for profile in profiles]


@router.get("/{profile_id}", response_model=ContentProfileResponse)
async def get_content_profile(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ContentProfileService, Depends(get_content_profile_service)],
) -> ContentProfileResponse:
    profile = await service.get(profile_id=profile_id, workspace_id=workspace_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        )
    return ContentProfileResponse.model_validate(profile)


@router.patch("/{profile_id}", response_model=ContentProfileResponse)
async def update_content_profile(
    profile_id: UUID,
    payload: ContentProfileUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ContentProfileService, Depends(get_content_profile_service)],
) -> ContentProfileResponse:
    profile = await service.update(
        profile_id=profile_id,
        workspace_id=workspace_id,
        type=payload.type,
        name=payload.name,
        description=payload.description,
        website=payload.website,
        location=payload.location,
        positioning=payload.positioning,
        topics=payload.topics,
        expertise=payload.expertise,
        goals=payload.goals,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        )
    return ContentProfileResponse.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_profile(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ContentProfileService, Depends(get_content_profile_service)],
) -> None:
    success = await service.delete(profile_id=profile_id, workspace_id=workspace_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        )
