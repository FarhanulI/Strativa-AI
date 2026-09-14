from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.content_intelligence.service import mark_synthesis_stale_and_invalidate
from app.core.database import async_session_factory
from app.infrastructure.cache.service import CacheService
from app.infrastructure.jobs.registry import register_handler
from app.infrastructure.jobs.service import submit_job
from app.infrastructure.redis_client import get_redis
from app.models.ai_job import AIJob, JobStatus
from app.models.content_profile import ContentProfile
from app.models.intelligence_analysis import (
    AnalysisGenerationSource,
    AudienceAnalysis,
    BrandAnalysis,
    MarketAnalysis,
)
from app.repositories.ai_job import AIJobRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.intelligence_analysis import IntelligenceAnalysisRepository
from app.services.ai.errors import AIError
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AITask
from app.services.intelligence.grounding import (
    GroundingResult,
    audience_grounding,
    brand_grounding,
    market_grounding,
)
from app.services.llm.intelligence_reasoner import IntelligenceReasoner

BRAND_SYSTEM_PROMPT = (
    "You are analyzing Brand Intelligence for a content profile. Identify strategic "
    "insights such as an underused content pillar relative to stated goals, or a "
    "tension between stated positioning and actual topic coverage. Only make claims "
    "grounded in the provided brand and profile data — do not invent brand facts the "
    "profile has not provided. Use likely, suggests, appears, or may indicate for "
    "interpretive claims."
)

AUDIENCE_SYSTEM_PROMPT = (
    "You are analyzing Audience Intelligence for a content profile. Synthesize "
    "personas, pain points, desires, questions, and objections into a coherent "
    "statement of what the audience actually needs next — connect scattered signals "
    "rather than treating each in isolation. Only make claims grounded in the "
    "provided audience data — do not invent audience facts. Use likely, suggests, "
    "appears, or may indicate for interpretive claims."
)

MARKET_SYSTEM_PROMPT = (
    "You are analyzing Market Intelligence for a content profile. Interpret topics, "
    "market signals, and competitors in the context of this specific profile's "
    "positioning and audience — a signal is only meaningful once connected to this "
    "profile's context, and must never be treated as a content-generation command "
    "on its own. Only make claims grounded in the provided market and profile data — "
    "do not invent market facts. Use likely, suggests, appears, or may indicate for "
    "interpretive claims."
)


@dataclass(frozen=True)
class DomainConfig:
    model: type[Any]
    task: AITask
    prompt_version: str
    system_prompt: str
    grounding_fn: Any


DOMAIN_CONFIGS: dict[str, DomainConfig] = {
    "brand": DomainConfig(
        model=BrandAnalysis,
        task=AITask.BRAND_ANALYSIS,
        prompt_version="brand_analysis_v1",
        system_prompt=BRAND_SYSTEM_PROMPT,
        grounding_fn=brand_grounding,
    ),
    "audience": DomainConfig(
        model=AudienceAnalysis,
        task=AITask.AUDIENCE_ANALYSIS,
        prompt_version="audience_analysis_v1",
        system_prompt=AUDIENCE_SYSTEM_PROMPT,
        grounding_fn=audience_grounding,
    ),
    "market": DomainConfig(
        model=MarketAnalysis,
        task=AITask.MARKET_ANALYSIS,
        prompt_version="market_analysis_v1",
        system_prompt=MARKET_SYSTEM_PROMPT,
        grounding_fn=market_grounding,
    ),
}


@dataclass
class AnalysisReadResult:
    analysis: Any | None = None
    pending_job: AIJob | None = None


def _insufficient_data_insights(grounding: GroundingResult) -> list[dict[str, str]]:
    return [{"summary": grounding.fallback_summary, "rationale": "insufficient_data"}]


def _ai_fallback_insights(grounding: GroundingResult) -> list[dict[str, str]]:
    return [{"summary": grounding.fallback_summary, "rationale": "ai_provider_unavailable"}]


class IntelligenceAnalysisService:
    """Read path used by the API: return the current analysis if it is still
    fresh against the domain's stored data, otherwise enqueue regeneration
    (Day 15 job queue) and return a pending marker. Never calls the AI Router
    itself — that only happens in the background job (see `generate` and the
    registered handlers below).
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.profile_repository = ContentProfileRepository(session)
        self.job_repository = AIJobRepository(session)

    async def get_or_enqueue(
        self, domain: str, profile_id: UUID, workspace_id: UUID, arq_pool: ArqRedis
    ) -> AnalysisReadResult:
        config = DOMAIN_CONFIGS[domain]
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")

        repository = IntelligenceAnalysisRepository(self.session, config.model)
        current = await repository.get_current(profile_id)
        grounding = config.grounding_fn(profile)

        if current is not None and current.source_fingerprint == grounding.fingerprint:
            return AnalysisReadResult(analysis=current)

        in_flight = await self._find_in_flight_job(profile_id, config.task.value)
        if in_flight is not None:
            return AnalysisReadResult(analysis=current, pending_job=in_flight)

        job = await submit_job(
            self.session,
            arq_pool,
            config.task.value,
            profile_id,
            {"profile_id": str(profile_id), "workspace_id": str(workspace_id)},
        )
        await self.session.commit()
        return AnalysisReadResult(analysis=current, pending_job=job)

    async def _find_in_flight_job(self, profile_id: UUID, task_type: str) -> AIJob | None:
        for status in (JobStatus.QUEUED, JobStatus.RUNNING):
            jobs = await self.job_repository.list_by_profile(
                profile_id, status=status, task_type=task_type, limit=1
            )
            if jobs:
                return jobs[0]
        return None


async def generate(session: AsyncSession, domain: str, profile_id: UUID, router: AIRouter) -> Any:
    """Run (or fall back on) the actual reasoning for one domain and persist
    it as the new current analysis. Called from the background job handler;
    never invoked synchronously from a request.
    """
    config = DOMAIN_CONFIGS[domain]
    profile = await session.get(ContentProfile, profile_id)
    if profile is None:
        raise ValueError("Content profile not found")

    grounding = config.grounding_fn(profile)
    repository = IntelligenceAnalysisRepository(session, config.model)

    if not grounding.sufficient:
        analysis = config.model(
            profile_id=profile_id,
            insights=_insufficient_data_insights(grounding),
            grounded_on=grounding.grounded_on,
            source_fingerprint=grounding.fingerprint,
            generation_source=AnalysisGenerationSource.INSUFFICIENT_DATA,
            analysis_version=config.prompt_version,
        )
    else:
        reasoner = IntelligenceReasoner(router, config.task, config.prompt_version)
        try:
            ai_result = await reasoner.reason(
                system_prompt=config.system_prompt, context=grounding.context
            )
            insights = [item.model_dump() for item in ai_result.output.insights]
            generation_source = AnalysisGenerationSource.AI
        except AIError:
            insights = _ai_fallback_insights(grounding)
            generation_source = AnalysisGenerationSource.AI_FALLBACK

        analysis = config.model(
            profile_id=profile_id,
            insights=insights,
            grounded_on=grounding.grounded_on,
            source_fingerprint=grounding.fingerprint,
            generation_source=generation_source,
            analysis_version=config.prompt_version,
        )

    await repository.clear_current(profile_id)
    await repository.create(analysis)
    # Any regeneration of a Brand/Audience/Market component invalidates the
    # profile's current strategic synthesis (see docs/development/day-17.md)
    # — synthesis itself regenerates lazily on next read, not eagerly here.
    await mark_synthesis_stale_and_invalidate(session, profile_id, profile.workspace_id)
    await session.commit()
    return analysis


async def _run_domain_job(domain: str, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = UUID(payload["profile_id"])
    workspace_id = payload["workspace_id"]
    async with async_session_factory() as session:
        router = AIRouter()
        analysis = await generate(session, domain, profile_id, router)

    # Must match app.api.v1.intelligence_analysis._cache_key exactly,
    # workspace_id included — that key is namespaced by workspace_id
    # specifically so a cache hit can never bypass the ownership check.
    await CacheService(get_redis()).invalidate(
        f"profile:{profile_id}:{domain}-analysis:workspace:{workspace_id}"
    )
    return {
        "analysis_id": str(analysis.id),
        "generation_source": analysis.generation_source.value,
    }


for _domain in DOMAIN_CONFIGS:
    register_handler(DOMAIN_CONFIGS[_domain].task.value, partial(_run_domain_job, _domain))
