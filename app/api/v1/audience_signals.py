from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.audience_signal import (
    AudienceSignalCreate,
    AudienceSignalResponse,
    AudienceSignalUpdate,
)
from app.services.audience_signal import AudienceSignalService

router = APIRouter(prefix="/profiles/{profile_id}/audience-signals", tags=["Audience Signals"])


async def get_audience_signal_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AudienceSignalService:
    return AudienceSignalService(session)


@router.post("", response_model=AudienceSignalResponse, status_code=status.HTTP_201_CREATED)
async def create_audience_signal(
    profile_id: UUID,
    payload: AudienceSignalCreate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[AudienceSignalService, Depends(get_audience_signal_service)],
) -> AudienceSignalResponse:
    try:
        signal = await service.create(profile_id, workspace_id, **payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Content profile not found") from error
    return AudienceSignalResponse.model_validate(signal)


@router.get("", response_model=list[AudienceSignalResponse])
async def list_audience_signals(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[AudienceSignalService, Depends(get_audience_signal_service)],
    signal_type: str | None = None,
    intent: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    source: str | None = None,
    sort_by: Annotated[str, Query(pattern="^(strength_score|observed_at)$")] = "observed_at",
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    skip: int = 0,
    limit: int = 100,
) -> list[AudienceSignalResponse]:
    try:
        signals = await service.list(
            profile_id,
            workspace_id,
            signal_type=signal_type,
            intent=intent,
            status=status_filter,
            source=source,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Content profile not found") from error
    return [AudienceSignalResponse.model_validate(signal) for signal in signals]


@router.get("/{signal_id}", response_model=AudienceSignalResponse)
async def get_audience_signal(
    profile_id: UUID,
    signal_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[AudienceSignalService, Depends(get_audience_signal_service)],
) -> AudienceSignalResponse:
    try:
        signal = await service.get(profile_id, signal_id, workspace_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Audience signal not found") from error
    if not signal:
        raise HTTPException(status_code=404, detail="Audience signal not found")
    return AudienceSignalResponse.model_validate(signal)


@router.patch("/{signal_id}", response_model=AudienceSignalResponse)
async def update_audience_signal(
    profile_id: UUID,
    signal_id: UUID,
    payload: AudienceSignalUpdate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[AudienceSignalService, Depends(get_audience_signal_service)],
) -> AudienceSignalResponse:
    try:
        signal = await service.update(
            profile_id, signal_id, workspace_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Audience signal not found") from error
    if not signal:
        raise HTTPException(status_code=404, detail="Audience signal not found")
    return AudienceSignalResponse.model_validate(signal)


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audience_signal(
    profile_id: UUID,
    signal_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[AudienceSignalService, Depends(get_audience_signal_service)],
) -> None:
    try:
        deleted = await service.delete(profile_id, signal_id, workspace_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Audience signal not found") from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Audience signal not found")
