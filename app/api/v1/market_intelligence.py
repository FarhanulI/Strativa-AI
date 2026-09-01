from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.market_intelligence import (
    MarketIntelligenceCreate,
    MarketIntelligenceResponse,
    MarketIntelligenceUpdate,
)
from app.services.market_intelligence import MarketIntelligenceService

router = APIRouter(
    prefix="/profiles/{profile_id}/market-intelligence",
    tags=["Market Intelligence"],
)


async def get_market_intelligence_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketIntelligenceService:
    return MarketIntelligenceService(session)


@router.post("", response_model=MarketIntelligenceResponse, status_code=status.HTTP_201_CREATED)
async def create_market_intelligence(
    profile_id: UUID,
    payload: MarketIntelligenceCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketIntelligenceService, Depends(get_market_intelligence_service)],
) -> MarketIntelligenceResponse:
    try:
        market_intelligence = await service.create(
            profile_id=profile_id,
            workspace_id=workspace_id,
            summary=payload.summary,
            market_context=payload.market_context,
        )
        return MarketIntelligenceResponse.model_validate(market_intelligence)
    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Market intelligence already exists for this content profile.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        ) from e


@router.get("", response_model=MarketIntelligenceResponse)
async def get_market_intelligence(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketIntelligenceService, Depends(get_market_intelligence_service)],
) -> MarketIntelligenceResponse:
    market_intelligence = await service.get(profile_id=profile_id, workspace_id=workspace_id)
    if not market_intelligence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found",
        )
    return MarketIntelligenceResponse.model_validate(market_intelligence)


@router.patch("", response_model=MarketIntelligenceResponse)
async def update_market_intelligence(
    profile_id: UUID,
    payload: MarketIntelligenceUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketIntelligenceService, Depends(get_market_intelligence_service)],
) -> MarketIntelligenceResponse:
    market_intelligence = await service.update(
        profile_id=profile_id,
        workspace_id=workspace_id,
        summary=payload.summary,
        market_context=payload.market_context,
    )
    if not market_intelligence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found",
        )
    return MarketIntelligenceResponse.model_validate(market_intelligence)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market_intelligence(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[MarketIntelligenceService, Depends(get_market_intelligence_service)],
) -> None:
    success = await service.delete(profile_id=profile_id, workspace_id=workspace_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found",
        )
