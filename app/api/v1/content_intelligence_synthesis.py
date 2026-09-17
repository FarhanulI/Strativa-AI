import json
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.content_intelligence.service import (
    ContentIntelligenceSynthesisService,
    synthesis_cache_key,
)
from app.core.config import settings
from app.core.database import get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.infrastructure.redis_client import get_redis
from app.models.ai_job import AIJob
from app.models.content_profile import ContentProfile
from app.schemas.content_intelligence_synthesis import (
    ContentIntelligenceSynthesisPendingResponse,
    ContentIntelligenceSynthesisResponse,
)

router = APIRouter(prefix="/profiles/{profile_id}", tags=["Content Intelligence Synthesis"])


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


def _serialize(synthesis) -> dict:
    return jsonable_encoder(
        ContentIntelligenceSynthesisResponse(
            id=synthesis.id,
            profile_id=synthesis.profile_id,
            summary=synthesis.summary,
            key_themes=synthesis.key_themes,
            supporting_analyses=synthesis.supporting_analyses,
            generation_source=synthesis.generation_source.value,
            is_current=synthesis.is_current,
            is_stale=synthesis.is_stale,
            cold_start=synthesis.cold_start,
            synthesis_version=synthesis.synthesis_version,
            generated_at=synthesis.generated_at,
        )
    )


def _pending_response(job: AIJob) -> JSONResponse:
    payload = ContentIntelligenceSynthesisPendingResponse(
        job_id=job.id, job_status=job.status.value
    )
    return JSONResponse(status_code=202, content=jsonable_encoder(payload))


@router.get("/synthesis")
async def get_synthesis(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    # A longer TTL than the component analyses: strategic synthesis is the
    # most expensive reasoning call in the system (see
    # docs/development/day-17.md's "Content Intelligence Synthesis Engine").
    redis = get_redis()
    key = synthesis_cache_key(profile.id, profile.workspace_id)
    cached = await redis.get(key)
    if cached is not None:
        return ContentIntelligenceSynthesisResponse(**json.loads(cached))

    service = ContentIntelligenceSynthesisService(session)
    try:
        result = await service.get_or_enqueue(profile.id, profile.workspace_id, arq_pool)
    except ValueError as error:
        raise not_found(error) from error

    if result.pending_job is not None:
        return _pending_response(result.pending_job)

    payload = _serialize(result.synthesis)
    await redis.set(key, json.dumps(payload), ex=settings.cache_synthesis_ttl_seconds)
    return ContentIntelligenceSynthesisResponse(**payload)
