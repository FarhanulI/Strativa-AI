from dataclasses import dataclass
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.content_intelligence.grounding import SynthesisGrounding, gather_synthesis_grounding
from app.content_intelligence.reasoner import SynthesisReasoner
from app.core.database import async_session_factory
from app.infrastructure.cache.service import CacheService
from app.infrastructure.jobs.registry import register_handler
from app.infrastructure.jobs.service import submit_job
from app.infrastructure.redis_client import get_redis
from app.models.ai_job import AIJob, JobStatus
from app.models.content_intelligence_synthesis import ContentIntelligenceSynthesis
from app.models.content_profile import ContentProfile
from app.models.intelligence_analysis import AnalysisGenerationSource
from app.repositories.ai_job import AIJobRepository
from app.repositories.content_intelligence_synthesis import ContentIntelligenceSynthesisRepository
from app.repositories.content_profile import ContentProfileRepository
from app.services.ai.errors import AIError
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AITask


def synthesis_cache_key(profile_id: UUID, workspace_id: UUID) -> str:
    # Namespaced by workspace_id for the same reason as the Day 16 analysis
    # cache key (see app.api.v1.intelligence_analysis._cache_key): a caller
    # who cannot prove ownership of profile_id must never get a cache hit.
    return f"profile:{profile_id}:synthesis:workspace:{workspace_id}"


async def mark_synthesis_stale_and_invalidate(
    session: AsyncSession, profile_id: UUID, workspace_id: UUID
) -> None:
    """Called by every component analysis (Brand/Audience/Market via
    `app.services.intelligence_analysis`, Performance via
    `app.services.performance_insight`) on successful regeneration.

    Only flips a flag and drops the cache entry -- the synthesis itself is
    regenerated lazily on the next GET (see `ContentIntelligenceSynthesisService
    .get_or_enqueue`), not eagerly here, to avoid thundering-herd
    regeneration when several components change close together.
    """
    repository = ContentIntelligenceSynthesisRepository(session)
    await repository.mark_stale(profile_id)
    await CacheService(get_redis()).invalidate(synthesis_cache_key(profile_id, workspace_id))


@dataclass
class SynthesisReadResult:
    synthesis: ContentIntelligenceSynthesis | None = None
    pending_job: AIJob | None = None


class ContentIntelligenceSynthesisService:
    """Read path used by the API: return the current synthesis if it isn't
    marked stale, otherwise enqueue regeneration (Day 15 job queue) and
    return a pending marker. Never calls the AI Router itself -- that only
    happens in the background job (see `generate_synthesis` and the
    registered handler below). Mirrors
    `app.services.intelligence_analysis.IntelligenceAnalysisService`.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.profile_repository = ContentProfileRepository(session)
        self.job_repository = AIJobRepository(session)

    async def get_or_enqueue(
        self, profile_id: UUID, workspace_id: UUID, arq_pool: ArqRedis
    ) -> SynthesisReadResult:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")

        repository = ContentIntelligenceSynthesisRepository(self.session)
        current = await repository.get_current(profile_id)
        if current is not None and not current.is_stale:
            return SynthesisReadResult(synthesis=current)

        in_flight = await self._find_in_flight_job(profile_id)
        if in_flight is not None:
            return SynthesisReadResult(synthesis=current, pending_job=in_flight)

        job = await submit_job(
            self.session,
            arq_pool,
            AITask.STRATEGIC_SYNTHESIS.value,
            profile_id,
            {"profile_id": str(profile_id), "workspace_id": str(workspace_id)},
        )
        await self.session.commit()
        return SynthesisReadResult(synthesis=current, pending_job=job)

    async def _find_in_flight_job(self, profile_id: UUID) -> AIJob | None:
        for status in (JobStatus.QUEUED, JobStatus.RUNNING):
            jobs = await self.job_repository.list_by_profile(
                profile_id,
                status=status,
                task_type=AITask.STRATEGIC_SYNTHESIS.value,
                limit=1,
            )
            if jobs:
                return jobs[0]
        return None


def _ai_fallback_summary(grounding: SynthesisGrounding) -> str:
    return (
        f"{grounding.component_count} of 4 intelligence domains "
        f"({', '.join(grounding.available_domains)}) have grounded analysis, but AI-generated "
        "synthesis is currently unavailable. Review each domain's analysis directly for "
        "strategic context."
    )


async def generate_synthesis(
    session: AsyncSession, profile_id: UUID, router: AIRouter
) -> ContentIntelligenceSynthesis:
    """Run (or fall back on) the actual cross-domain reasoning and persist it
    as the new current synthesis. Called from the background job handler;
    never invoked synchronously from a request.
    """
    profile = await session.get(ContentProfile, profile_id)
    if profile is None:
        raise ValueError("Content profile not found")

    grounding = await gather_synthesis_grounding(session, profile_id)
    repository = ContentIntelligenceSynthesisRepository(session)

    if not grounding.sufficient:
        synthesis = ContentIntelligenceSynthesis(
            profile_id=profile_id,
            summary=grounding.fallback_summary,
            key_themes=[],
            supporting_analyses=grounding.supporting_analyses,
            generation_source=AnalysisGenerationSource.INSUFFICIENT_DATA,
            is_stale=False,
        )
    else:
        reasoner = SynthesisReasoner(router)
        try:
            ai_result = await reasoner.reason(context=grounding.context)
            summary = ai_result.output.summary
            key_themes = ai_result.output.key_themes
            generation_source = AnalysisGenerationSource.AI
        except AIError:
            summary = _ai_fallback_summary(grounding)
            key_themes = list(grounding.available_domains)
            generation_source = AnalysisGenerationSource.AI_FALLBACK

        synthesis = ContentIntelligenceSynthesis(
            profile_id=profile_id,
            summary=summary,
            key_themes=key_themes,
            supporting_analyses=grounding.supporting_analyses,
            generation_source=generation_source,
            is_stale=False,
        )

    await repository.clear_current(profile_id)
    await repository.create(synthesis)
    await session.commit()
    return synthesis


async def _run_synthesis_job(payload: dict) -> dict:
    profile_id = UUID(payload["profile_id"])
    workspace_id = UUID(payload["workspace_id"])
    async with async_session_factory() as session:
        router = AIRouter()
        synthesis = await generate_synthesis(session, profile_id, router)

    await CacheService(get_redis()).invalidate(synthesis_cache_key(profile_id, workspace_id))
    return {
        "synthesis_id": str(synthesis.id),
        "generation_source": synthesis.generation_source.value,
    }


register_handler(AITask.STRATEGIC_SYNTHESIS.value, _run_synthesis_job)
