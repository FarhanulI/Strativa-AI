from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.pain_point import PainPointCreate, PainPointResponse, PainPointUpdate
from app.services.pain_point import PainPointService

router = APIRouter(
    prefix="/audience-intelligence/{audience_id}/pain-points",
    tags=["Pain Points"],
)


async def get_pain_point_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PainPointService:
    return PainPointService(session)


@router.post("", response_model=PainPointResponse, status_code=status.HTTP_201_CREATED)
async def create_pain_point(
    audience_id: UUID,
    payload: PainPointCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[PainPointService, Depends(get_pain_point_service)],
) -> PainPointResponse:
    try:
        pain_point = await service.create(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            severity=payload.severity,
            frequency=payload.frequency,
        )
        return PainPointResponse.model_validate(pain_point)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[PainPointResponse])
async def list_pain_points(
    audience_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[PainPointService, Depends(get_pain_point_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[PainPointResponse]:
    try:
        pain_points = await service.list(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [PainPointResponse.model_validate(p) for p in pain_points]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("/{pain_point_id}", response_model=PainPointResponse)
async def get_pain_point(
    audience_id: UUID,
    pain_point_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[PainPointService, Depends(get_pain_point_service)],
) -> PainPointResponse:
    try:
        pain_point = await service.get(
            audience_intelligence_id=audience_id,
            pain_point_id=pain_point_id,
            workspace_id=workspace_id,
        )
        if not pain_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pain point not found",
            )
        return PainPointResponse.model_validate(pain_point)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.patch("/{pain_point_id}", response_model=PainPointResponse)
async def update_pain_point(
    audience_id: UUID,
    pain_point_id: UUID,
    payload: PainPointUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[PainPointService, Depends(get_pain_point_service)],
) -> PainPointResponse:
    try:
        pain_point = await service.update(
            audience_intelligence_id=audience_id,
            pain_point_id=pain_point_id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            severity=payload.severity,
            frequency=payload.frequency,
        )
        if not pain_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pain point not found",
            )
        return PainPointResponse.model_validate(pain_point)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.delete("/{pain_point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pain_point(
    audience_id: UUID,
    pain_point_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[PainPointService, Depends(get_pain_point_service)],
) -> None:
    try:
        success = await service.delete(
            audience_intelligence_id=audience_id,
            pain_point_id=pain_point_id,
            workspace_id=workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pain point not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e
