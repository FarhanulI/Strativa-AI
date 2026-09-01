from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.brand import BrandCreate, BrandResponse, BrandUpdate
from app.services.brand import BrandService

router = APIRouter(prefix="/profiles", tags=["Brands"])


async def get_brand_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BrandService:
    return BrandService(session)


@router.post(
    "/{profile_id}/brand",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_brand(
    profile_id: UUID,
    payload: BrandCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[BrandService, Depends(get_brand_service)],
) -> BrandResponse:
    """
    Create a new brand profile for a content profile.

    Temporary: workspace_id is provided as a query parameter.
    This will later be derived from the authenticated user's workspace membership.
    """
    try:
        brand = await service.create(
            profile_id=profile_id,
            workspace_id=workspace_id,
            positioning=payload.positioning,
            mission=payload.mission,
            vision=payload.vision,
            unique_selling_proposition=payload.unique_selling_proposition,
            values=payload.values,
            personality=payload.personality,
            voice=payload.voice,
            tone=payload.tone,
            messaging_guidelines=payload.messaging_guidelines,
            visual_identity=payload.visual_identity,
        )
        return BrandResponse.model_validate(brand)
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{profile_id}/brand", response_model=BrandResponse)
async def get_brand(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[BrandService, Depends(get_brand_service)],
) -> BrandResponse:
    """
    Get the brand profile for a content profile within a workspace.
    """
    brand = await service.get(profile_id, workspace_id)
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )
    return BrandResponse.model_validate(brand)


@router.patch("/{profile_id}/brand", response_model=BrandResponse)
async def update_brand(
    profile_id: UUID,
    payload: BrandUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[BrandService, Depends(get_brand_service)],
) -> BrandResponse:
    """
    Update a brand profile for a content profile within a workspace.
    """
    brand = await service.update(
        profile_id=profile_id,
        workspace_id=workspace_id,
        positioning=payload.positioning,
        mission=payload.mission,
        vision=payload.vision,
        unique_selling_proposition=payload.unique_selling_proposition,
        values=payload.values,
        personality=payload.personality,
        voice=payload.voice,
        tone=payload.tone,
        messaging_guidelines=payload.messaging_guidelines,
        visual_identity=payload.visual_identity,
    )
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )
    return BrandResponse.model_validate(brand)


@router.delete("/{profile_id}/brand", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[BrandService, Depends(get_brand_service)],
) -> None:
    """
    Delete the brand profile for a content profile within a workspace.
    """
    success = await service.delete(profile_id, workspace_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )
