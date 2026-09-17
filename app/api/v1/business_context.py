from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.models.content_profile import ContentProfile
from app.schemas.business_context import (
    BusinessContextCreate,
    BusinessContextResponse,
    BusinessContextUpdate,
)
from app.services.business_context import BusinessContextService

router = APIRouter(prefix="/profiles", tags=["Business Context"])


async def get_business_context_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BusinessContextService:
    return BusinessContextService(session)


@router.post(
    "/{profile_id}/business-context",
    response_model=BusinessContextResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_context(
    payload: BusinessContextCreate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[BusinessContextService, Depends(get_business_context_service)],
) -> BusinessContextResponse:
    """
    Create a new business context for a content profile.

    Business context is optional and can be created for both creators and businesses.
    """
    try:
        context = await service.create(
            profile_id=profile.id,
            workspace_id=profile.workspace_id,
            commercial_objectives=payload.commercial_objectives,
            target_market=payload.target_market,
            pricing_position=payload.pricing_position,
        )
        return BusinessContextResponse.model_validate(context)
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


@router.get("/{profile_id}/business-context", response_model=BusinessContextResponse)
async def get_business_context(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[BusinessContextService, Depends(get_business_context_service)],
) -> BusinessContextResponse:
    """
    Get the business context for a content profile within a workspace.
    """
    context = await service.get(profile.id, profile.workspace_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business context not found",
        )
    return BusinessContextResponse.model_validate(context)


@router.patch("/{profile_id}/business-context", response_model=BusinessContextResponse)
async def update_business_context(
    payload: BusinessContextUpdate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[BusinessContextService, Depends(get_business_context_service)],
) -> BusinessContextResponse:
    """
    Update a business context for a content profile within a workspace.
    """
    context = await service.update(
        profile_id=profile.id,
        workspace_id=profile.workspace_id,
        commercial_objectives=payload.commercial_objectives,
        target_market=payload.target_market,
        pricing_position=payload.pricing_position,
    )
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business context not found",
        )
    return BusinessContextResponse.model_validate(context)


@router.delete("/{profile_id}/business-context", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business_context(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[BusinessContextService, Depends(get_business_context_service)],
) -> None:
    """
    Delete a business context for a content profile within a workspace.
    """
    deleted = await service.delete(profile.id, profile.workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business context not found",
        )
