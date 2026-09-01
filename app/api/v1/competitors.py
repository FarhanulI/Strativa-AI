from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.competitor import CompetitorCreate, CompetitorResponse, CompetitorUpdate
from app.services.competitor import CompetitorService

router = APIRouter(
    prefix="/market-intelligence/{market_id}/competitors",
    tags=["Competitors"],
)


async def get_competitor_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompetitorService:
    return CompetitorService(session)


@router.post("", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor(
    market_id: UUID,
    payload: CompetitorCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[CompetitorService, Depends(get_competitor_service)],
) -> CompetitorResponse:
    try:
        competitor = await service.create(
            market_intelligence_id=market_id,
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            platform=payload.platform,
            profile_url=payload.profile_url,
            niche=payload.niche,
            relevance_score=payload.relevance_score,
            competitor_metadata=payload.competitor_metadata,
        )
        return CompetitorResponse.model_validate(competitor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[CompetitorResponse])
async def list_competitors(
    market_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[CompetitorService, Depends(get_competitor_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[CompetitorResponse]:
    try:
        competitors = await service.list(
            market_intelligence_id=market_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
        return [CompetitorResponse.model_validate(c) for c in competitors]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    market_id: UUID,
    competitor_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[CompetitorService, Depends(get_competitor_service)],
) -> CompetitorResponse:
    try:
        competitor = await service.get(
            market_intelligence_id=market_id,
            competitor_id=competitor_id,
            workspace_id=workspace_id,
        )
        if not competitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitor not found",
            )
        return CompetitorResponse.model_validate(competitor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.patch("/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    market_id: UUID,
    competitor_id: UUID,
    payload: CompetitorUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[CompetitorService, Depends(get_competitor_service)],
) -> CompetitorResponse:
    try:
        competitor = await service.update(
            market_intelligence_id=market_id,
            competitor_id=competitor_id,
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            platform=payload.platform,
            profile_url=payload.profile_url,
            niche=payload.niche,
            relevance_score=payload.relevance_score,
            competitor_metadata=payload.competitor_metadata,
        )
        if not competitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitor not found",
            )
        return CompetitorResponse.model_validate(competitor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    market_id: UUID,
    competitor_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[CompetitorService, Depends(get_competitor_service)],
) -> None:
    try:
        success = await service.delete(
            market_intelligence_id=market_id,
            competitor_id=competitor_id,
            workspace_id=workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitor not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e
