from typing import Annotated
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.models.ai_job import AIJob
from app.models.content_profile import ContentProfile
from app.schemas.content_performance import (
    ContentPerformanceCreate,
    ContentPerformanceResponse,
    ContentPerformanceUpdate,
    PerformanceAnalysisPendingResponse,
    PerformanceInsightResponse,
    PerformanceMetricsEntryCreate,
    PerformanceMetricsEntryResponse,
)
from app.services.ai.errors import AIError
from app.services.ai.router import AIRouter
from app.services.content_performance import ContentPerformanceService, DuplicateReportingPeriodError
from app.services.llm.performance_reasoner import PerformanceReasoner
from app.services.performance_insight import PerformanceInsightService

router = APIRouter(prefix="/profiles/{profile_id}", tags=["Performance Intelligence"])


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


def _pending_analysis_response(
    content_performance_id: UUID, job: AIJob
) -> JSONResponse:
    payload = PerformanceAnalysisPendingResponse(
        content_performance_id=content_performance_id, job_id=job.id, job_status=job.status.value
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content=jsonable_encoder(payload)
    )


async def get_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentPerformanceService:
    return ContentPerformanceService(session)


@router.post("/performance", response_model=ContentPerformanceResponse, status_code=201)
async def create(
    payload: ContentPerformanceCreate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        return await service.create(profile.id, profile.workspace_id, **payload.model_dump())
    except ValueError as error:
        raise not_found(error) from error


@router.get("/performance", response_model=list[ContentPerformanceResponse])
async def list_performance(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
    platform: str | None = None,
    format: str | None = None,
    topic: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    try:
        return await service.list(
            profile.id,
            profile.workspace_id,
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
    performance_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        result = await service.get(profile.id, profile.workspace_id, performance_id)
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Content performance not found")
    return result


@router.patch("/performance/{performance_id}", response_model=ContentPerformanceResponse)
async def update(
    performance_id: UUID,
    payload: ContentPerformanceUpdate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        result = await service.update(
            profile.id,
            profile.workspace_id,
            performance_id,
            **payload.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Content performance not found")
    return result


@router.delete("/performance/{performance_id}", status_code=204)
async def delete(
    performance_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
):
    try:
        result = await service.delete(profile.id, profile.workspace_id, performance_id)
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Content performance not found")


@router.post("/published/{published_id}/metrics", status_code=status.HTTP_202_ACCEPTED)
async def submit_metrics(
    published_id: UUID,
    payload: PerformanceMetricsEntryCreate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
) -> JSONResponse:
    try:
        record, job = await service.submit_metrics(
            profile.id,
            profile.workspace_id,
            published_id,
            arq_pool,
            **payload.model_dump(),
        )
    except DuplicateReportingPeriodError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise not_found(error) from error
    response = PerformanceMetricsEntryResponse(
        content_performance_id=record.id, job_id=job.id, job_status=job.status.value
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content=jsonable_encoder(response)
    )


@router.post("/performance/{performance_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze(
    performance_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentPerformanceService, Depends(get_service)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
) -> JSONResponse:
    try:
        job = await service.enqueue_analysis(
            profile.id, profile.workspace_id, performance_id, arq_pool
        )
    except ValueError as error:
        raise not_found(error) from error
    return _pending_analysis_response(performance_id, job)


def insight_service(session: AsyncSession) -> PerformanceInsightService:
    return PerformanceInsightService(session, PerformanceReasoner(AIRouter()))


@router.post("/performance/{performance_id}/insights", response_model=PerformanceInsightResponse)
async def create_insight(
    performance_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        return await insight_service(session).create(
            profile.id, profile.workspace_id, performance_id
        )
    except ValueError as error:
        raise not_found(error) from error
    except AIError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get(
    "/performance/{performance_id}/insights", response_model=list[PerformanceInsightResponse]
)
async def record_insights(
    performance_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        return await insight_service(session).list_for_record(
            profile.id, profile.workspace_id, performance_id
        )
    except ValueError as error:
        raise not_found(error) from error


@router.get("/performance-insights", response_model=list[PerformanceInsightResponse])
async def profile_insights(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    insight_type: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    minimum_confidence: float | None = Query(None, ge=0, le=1),
):
    try:
        return await insight_service(session).list_for_profile(
            profile.id,
            profile.workspace_id,
            insight_type=insight_type,
            status=status_filter,
            minimum_confidence=minimum_confidence,
        )
    except ValueError as error:
        raise not_found(error) from error
