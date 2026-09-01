from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.market_signal import (
    MarketSignalCreate,
    MarketSignalResponse,
    MarketSignalUpdate,
)
from app.services.market_signal import MarketSignalService

router = APIRouter(
    prefix="/market-intelligence/{market_id}/signals",
    tags=["Market Signals"],
)


async def get_market_signal_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketSignalService:
    return MarketSignalService(session)


@router.post("", response_model=MarketSignalResponse, status_code=status.HTTP_201_CREATED)
async def create_market_signal(
    market_id: UUID,
    payload: MarketSignalCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketSignalService, Depends(get_market_signal_service)],
) -> MarketSignalResponse:
    try:
        signal = await service.create(
            market_intelligence_id=market_id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            topic_id=payload.topic_id,
            source_type=payload.source_type,
            source_url=payload.source_url,
            signal_type=payload.signal_type,
            velocity_score=payload.velocity_score,
            relevance_score=payload.relevance_score,
            engagement_score=payload.engagement_score,
            status=payload.status,
            detected_at=payload.detected_at,
            expires_at=payload.expires_at,
            signal_metadata=payload.signal_metadata,
        )
        return MarketSignalResponse.model_validate(signal)
    except ValueError as e:
        message = str(e)
        if "Topic does not belong" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[MarketSignalResponse])
async def list_market_signals(
    market_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketSignalService, Depends(get_market_signal_service)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    signal_type: Annotated[str | None, Query()] = None,
    topic_id: Annotated[UUID | None, Query()] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[MarketSignalResponse]:
    try:
        signals = await service.list(
            market_intelligence_id=market_id,
            workspace_id=workspace_id,
            status=status_filter,
            signal_type=signal_type,
            topic_id=topic_id,
            skip=skip,
            limit=limit,
        )
        return [MarketSignalResponse.model_validate(s) for s in signals]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.get("/{signal_id}", response_model=MarketSignalResponse)
async def get_market_signal(
    market_id: UUID,
    signal_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketSignalService, Depends(get_market_signal_service)],
) -> MarketSignalResponse:
    try:
        signal = await service.get(
            market_intelligence_id=market_id,
            signal_id=signal_id,
            workspace_id=workspace_id,
        )
        if not signal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Market signal not found",
            )
        return MarketSignalResponse.model_validate(signal)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.patch("/{signal_id}", response_model=MarketSignalResponse)
async def update_market_signal(
    market_id: UUID,
    signal_id: UUID,
    payload: MarketSignalUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketSignalService, Depends(get_market_signal_service)],
) -> MarketSignalResponse:
    try:
        signal = await service.update(
            market_intelligence_id=market_id,
            signal_id=signal_id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            topic_id=payload.topic_id,
            source_type=payload.source_type,
            source_url=payload.source_url,
            signal_type=payload.signal_type,
            velocity_score=payload.velocity_score,
            relevance_score=payload.relevance_score,
            engagement_score=payload.engagement_score,
            status=payload.status,
            detected_at=payload.detected_at,
            expires_at=payload.expires_at,
            signal_metadata=payload.signal_metadata,
        )
        if not signal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Market signal not found",
            )
        return MarketSignalResponse.model_validate(signal)
    except ValueError as e:
        message = str(e)
        if "Topic does not belong" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market_signal(
    market_id: UUID,
    signal_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketSignalService, Depends(get_market_signal_service)],
) -> None:
    try:
        success = await service.delete(
            market_intelligence_id=market_id,
            signal_id=signal_id,
            workspace_id=workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Market signal not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e
