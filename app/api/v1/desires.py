from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.desire import DesireCreate, DesireResponse, DesireUpdate
from app.services.desire import DesireService

router = APIRouter(
    prefix="/audience-intelligence/{audience_id}/desires",
    tags=["Desires"],
)


async def get_desire_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DesireService:
    return DesireService(session)


@router.post("", response_model=DesireResponse, status_code=status.HTTP_201_CREATED)
async def create_desire(
    audience_id: UUID,
    payload: DesireCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[DesireService, Depends(get_desire_service)],
) -> DesireResponse:
    try:
        desire = await service.create(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            importance=payload.importance,
        )
        return DesireResponse.model_validate(desire)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[DesireResponse])
async def list_desires(
    audience_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[DesireService, Depends(get_desire_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[DesireResponse]:
    try:
        desires = await service.list(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [DesireResponse.model_validate(d) for d in desires]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("/{desire_id}", response_model=DesireResponse)
async def get_desire(
    audience_id: UUID,
    desire_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[DesireService, Depends(get_desire_service)],
) -> DesireResponse:
    try:
        desire = await service.get(
            audience_intelligence_id=audience_id,
            desire_id=desire_id,
            workspace_id=workspace_id,
        )
        if not desire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Desire not found",
            )
        return DesireResponse.model_validate(desire)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.patch("/{desire_id}", response_model=DesireResponse)
async def update_desire(
    audience_id: UUID,
    desire_id: UUID,
    payload: DesireUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[DesireService, Depends(get_desire_service)],
) -> DesireResponse:
    try:
        desire = await service.update(
            audience_intelligence_id=audience_id,
            desire_id=desire_id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            importance=payload.importance,
        )
        if not desire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Desire not found",
            )
        return DesireResponse.model_validate(desire)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.delete("/{desire_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_desire(
    audience_id: UUID,
    desire_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[DesireService, Depends(get_desire_service)],
) -> None:
    try:
        success = await service.delete(
            audience_intelligence_id=audience_id,
            desire_id=desire_id,
            workspace_id=workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Desire not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e
