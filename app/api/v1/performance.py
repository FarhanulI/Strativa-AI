from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.content_performance import (
    ContentPerformanceCreate,
    ContentPerformanceResponse,
    ContentPerformanceUpdate,
    PerformanceAnalysisResponse,
    PerformanceInsightResponse,
)
from app.services.ai.errors import AIError
from app.services.ai.router import AIRouter
from app.services.content_performance import ContentPerformanceService
from app.services.llm.performance_reasoner import PerformanceReasoner
from app.services.performance_insight import PerformanceInsightService

router = APIRouter(prefix="/profiles/{profile_id}", tags=["Performance Intelligence"])


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


async def get_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentPerformanceService:
    return ContentPerformanceService(session)


@router.post("/performance", response_model=ContentPerformanceResponse, status_code=201)
async def create(
    profile_id: UUID,
    payload: ContentPerformanceCreate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        return await service.create(profile_id, workspace_id, **payload.model_dump())
    except ValueError as error:
        raise not_found(error) from error


@router.get("/performance", response_model=list[ContentPerformanceResponse])
async def list_performance(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
    platform: str | None = None,
    format: str | None = None,
    topic: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    try:
        return await service.list(
            profile_id,
            workspace_id,
            platform=platform,
            format=format,
            topic=topic,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise not_found(error) from error


@router.get("/performance/{performance_id}", response_model=ContentPerformanceResponse)
async def get(
    profile_id: UUID,
    performance_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        result = await service.get(profile_id, workspace_id, performance_id)
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Content performance not found")
    return result


@router.patch("/performance/{performance_id}", response_model=ContentPerformanceResponse)
async def update(
    profile_id: UUID,
    performance_id: UUID,
    payload: ContentPerformanceUpdate,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        result = await service.update(
            profile_id, workspace_id, performance_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Content performance not found")
    return result


@router.delete("/performance/{performance_id}", status_code=204)
async def delete(
    profile_id: UUID,
    performance_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        result = await service.delete(profile_id, workspace_id, performance_id)
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Content performance not found")


@router.post("/performance/{performance_id}/analyze", response_model=PerformanceAnalysisResponse)
async def analyze(
    profile_id: UUID,
    performance_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        return await service.analyze(profile_id, workspace_id, performance_id)
    except ValueError as error:
        raise not_found(error) from error


def insight_service(session: AsyncSession) -> PerformanceInsightService:
    return PerformanceInsightService(session, PerformanceReasoner(AIRouter()))


@router.post("/performance/{performance_id}/insights", response_model=PerformanceInsightResponse)
async def create_insight(
    profile_id: UUID,
    performance_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        return await insight_service(session).create(profile_id, workspace_id, performance_id)
    except ValueError as error:
        raise not_found(error) from error
    except AIError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get(
    "/performance/{performance_id}/insights", response_model=list[PerformanceInsightResponse]
)
async def record_insights(
    profile_id: UUID,
    performance_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        return await insight_service(session).list_for_record(
            profile_id, workspace_id, performance_id
        )
    except ValueError as error:
        raise not_found(error) from error


@router.get("/performance-insights", response_model=list[PerformanceInsightResponse])
async def profile_insights(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    insight_type: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    minimum_confidence: float | None = Query(None, ge=0, le=1),
):
    try:
        return await insight_service(session).list_for_profile(
            profile_id,
            workspace_id,
            insight_type=insight_type,
            status=status_filter,
            minimum_confidence=minimum_confidence,
        )
    except ValueError as error:
        raise not_found(error) from error
