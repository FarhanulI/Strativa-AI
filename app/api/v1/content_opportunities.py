from typing import Annotated
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.schemas.content_opportunity import (
    ContentOpportunityCreate,
    ContentOpportunityResponse,
    ContentOpportunityUpdate,
)
from app.services.content_opportunity import ContentOpportunityService

router = APIRouter(prefix="/profiles/{profile_id}/opportunities", tags=["Content Opportunities"])


async def get_content_opportunity_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentOpportunityService:
    return ContentOpportunityService(session)


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("", response_model=ContentOpportunityResponse, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    profile_id: UUID,
    payload: ContentOpportunityCreate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentOpportunityService, Depends(get_content_opportunity_service)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
) -> ContentOpportunityResponse:
    try:
        opportunity = await service.create(
            profile_id, workspace_id, arq_pool, **payload.model_dump()
        )
    except ValueError as error:
        raise not_found(error) from error
    return ContentOpportunityResponse.model_validate(opportunity)


@router.get("", response_model=list[ContentOpportunityResponse])
async def list_opportunities(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentOpportunityService, Depends(get_content_opportunity_service)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    source_signal: str | None = None,
    target_objective: str | None = None,
    priority: str | None = None,
    sort: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    skip: int = 0,
    limit: int = 100,
) -> list[ContentOpportunityResponse]:
    try:
        opportunities = await service.list(
            profile_id,
            workspace_id,
            status=status_filter,
            source_signal=source_signal,
            target_objective=target_objective,
            priority=priority,
            sort_order=sort,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise not_found(error) from error
    return [ContentOpportunityResponse.model_validate(item) for item in opportunities]


@router.get("/{opportunity_id}", response_model=ContentOpportunityResponse)
async def get_opportunity(
    profile_id: UUID,
    opportunity_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentOpportunityService, Depends(get_content_opportunity_service)],
) -> ContentOpportunityResponse:
    try:
        opportunity = await service.get(profile_id, opportunity_id, workspace_id)
    except ValueError as error:
        raise not_found(error) from error
    if not opportunity:
        raise HTTPException(status_code=404, detail="Content opportunity not found")
    return ContentOpportunityResponse.model_validate(opportunity)


@router.patch("/{opportunity_id}", response_model=ContentOpportunityResponse)
async def update_opportunity(
    profile_id: UUID,
    opportunity_id: UUID,
    payload: ContentOpportunityUpdate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentOpportunityService, Depends(get_content_opportunity_service)],
) -> ContentOpportunityResponse:
    try:
        opportunity = await service.update(
            profile_id, opportunity_id, workspace_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise not_found(error) from error
    if not opportunity:
        raise HTTPException(status_code=404, detail="Content opportunity not found")
    return ContentOpportunityResponse.model_validate(opportunity)


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    profile_id: UUID,
    opportunity_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentOpportunityService, Depends(get_content_opportunity_service)],
) -> None:
    try:
        deleted = await service.delete(profile_id, opportunity_id, workspace_id)
    except ValueError as error:
        raise not_found(error) from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Content opportunity not found")
