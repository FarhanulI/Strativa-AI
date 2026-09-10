from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.content_draft_variation import VariationType
from app.schemas.content_draft_variation import (
    ContentDraftVariationGenerateRequest,
    ContentDraftVariationResponse,
    ContentDraftVariationSelectRequest,
)
from app.services.content_creation.variation_service import ContentDraftVariationService

router = APIRouter(tags=["Content Draft Variations"])


async def get_variation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentDraftVariationService:
    return ContentDraftVariationService(session)


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/profiles/{profile_id}/drafts/{draft_id}/variations",
    response_model=list[ContentDraftVariationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_variations(
    profile_id: UUID,
    draft_id: UUID,
    payload: ContentDraftVariationGenerateRequest,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentDraftVariationService, Depends(get_variation_service)],
) -> list[ContentDraftVariationResponse]:
    try:
        variations = await service.generate(
            profile_id,
            draft_id,
            workspace_id,
            variation_type=payload.variation_type,
            count=payload.count,
            use_ai=payload.use_ai,
        )
    except ValueError as error:
        message = str(error)
        if "conflict" in message.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from error
        raise not_found(error) from error
    return [ContentDraftVariationResponse.model_validate(v) for v in variations]


@router.get(
    "/profiles/{profile_id}/drafts/{draft_id}/variations",
    response_model=list[ContentDraftVariationResponse],
)
async def list_variations(
    profile_id: UUID,
    draft_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentDraftVariationService, Depends(get_variation_service)],
    variation_type: VariationType | None = None,
) -> list[ContentDraftVariationResponse]:
    try:
        variations = await service.list(profile_id, draft_id, workspace_id, variation_type)
    except ValueError as error:
        raise not_found(error) from error
    return [ContentDraftVariationResponse.model_validate(v) for v in variations]


@router.patch(
    "/profiles/{profile_id}/drafts/{draft_id}/variations/{variation_id}",
    response_model=ContentDraftVariationResponse,
)
async def select_variation(
    profile_id: UUID,
    draft_id: UUID,
    variation_id: UUID,
    payload: ContentDraftVariationSelectRequest,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentDraftVariationService, Depends(get_variation_service)],
) -> ContentDraftVariationResponse:
    try:
        variation = await service.select(
            profile_id, draft_id, variation_id, workspace_id, payload.is_selected
        )
    except ValueError as error:
        message = str(error)
        if "not found" in message.lower():
            raise not_found(error) from error
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from error
    return ContentDraftVariationResponse.model_validate(variation)
