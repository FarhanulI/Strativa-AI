import json
from typing import Annotated
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.infrastructure.redis_client import get_redis
from app.models.ai_job import AIJob
from app.schemas.intelligence_analysis import (
    IntelligenceAnalysisPendingResponse,
    IntelligenceAnalysisResponse,
)
from app.services.intelligence_analysis import IntelligenceAnalysisService

router = APIRouter(prefix="/profiles/{profile_id}", tags=["Intelligence Reasoning"])


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


def _cache_key(profile_id: UUID, domain: str, workspace_id: UUID) -> str:
    # workspace_id is part of the key (not just an argument checked after a
    # hit) so that a caller who cannot prove ownership of profile_id can
    # never get a cache hit for it: a wrong workspace_id produces a
    # different key, misses, and falls through to get_or_enqueue's real
    # ownership check (404), rather than short-circuiting past it.
    return f"profile:{profile_id}:{domain}-analysis:workspace:{workspace_id}"


def _serialize(analysis) -> dict:
    return jsonable_encoder(
        IntelligenceAnalysisResponse(
            id=analysis.id,
            profile_id=analysis.profile_id,
            insights=analysis.insights,
            grounded_on=analysis.grounded_on,
            generation_source=analysis.generation_source.value,
            is_current=analysis.is_current,
            analysis_version=analysis.analysis_version,
            generated_at=analysis.generated_at,
        )
    )


def _pending_response(job: AIJob) -> JSONResponse:
    payload = IntelligenceAnalysisPendingResponse(job_id=job.id, job_status=job.status.value)
    return JSONResponse(status_code=202, content=jsonable_encoder(payload))


async def _get_analysis(
    profile_id: UUID,
    domain: str,
    workspace_id: UUID,
    session: AsyncSession,
    arq_pool: ArqRedis,
):
    # The freshness check itself requires loading the domain's full record
    # graph (to compute a fingerprint), so caching only helps once a result
    # is known fresh — a cache hit here skips that DB round trip entirely.
    # Correctness relies on explicit invalidation at regeneration time
    # (see app.services.intelligence_analysis._run_domain_job), not the TTL.
    redis = get_redis()
    key = _cache_key(profile_id, domain, workspace_id)
    cached = await redis.get(key)
    if cached is not None:
        return IntelligenceAnalysisResponse(**json.loads(cached))

    service = IntelligenceAnalysisService(session)
    try:
        result = await service.get_or_enqueue(domain, profile_id, workspace_id, arq_pool)
    except ValueError as error:
        raise not_found(error) from error

    if result.pending_job is not None:
        return _pending_response(result.pending_job)

    payload = _serialize(result.analysis)
    await redis.set(key, json.dumps(payload), ex=settings.cache_default_ttl_seconds)
    return IntelligenceAnalysisResponse(**payload)


@router.get("/brand-analysis")
async def get_brand_analysis(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    return await _get_analysis(profile_id, "brand", workspace_id, session, arq_pool)


@router.get("/audience-analysis")
async def get_audience_analysis(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    return await _get_analysis(profile_id, "audience", workspace_id, session, arq_pool)


@router.get("/market-analysis")
async def get_market_analysis(
    profile_id: UUID,
    workspace_id: Annotated[UUID, Query(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    return await _get_analysis(profile_id, "market", workspace_id, session, arq_pool)
