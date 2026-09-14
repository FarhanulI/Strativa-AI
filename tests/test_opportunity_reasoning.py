import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import fakeredis.aioredis as fakeredis
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.jobs.service import submit_job
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.models.ai_job import JobStatus
from app.models.content_intelligence_synthesis import ContentIntelligenceSynthesis
from app.models.content_opportunity import (
    OpportunitySource,
    RationaleGenerationSource,
    TargetObjective,
)
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.intelligence_analysis import AnalysisGenerationSource
from app.models.market_intelligence import MarketIntelligence
from app.models.market_signal import MarketSignal
from app.models.workspace import Workspace
from app.repositories.content_intelligence_synthesis import ContentIntelligenceSynthesisRepository
from app.schemas.content_opportunity import OpportunityRationaleLLMResult
from app.services.ai.errors import AIProviderRequestError
from app.services.ai.registry import AIModelConfig, ModelRegistry, ProviderRegistry
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AICapability
from app.services.content_opportunity import ContentOpportunityService
from app.services.opportunity_reasoning import generate_rationale


@pytest.fixture(autouse=True)
def _use_test_session_for_worker(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession):
    @asynccontextmanager
    async def _factory():
        yield db_session

    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.async_session_factory", _factory)
    monkeypatch.setattr("app.services.opportunity_reasoning.async_session_factory", _factory)


@pytest.fixture(autouse=True)
def _fake_ratelimit_redis(monkeypatch: pytest.MonkeyPatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.services.opportunity_reasoning.get_redis", lambda: fake)
    yield fake


async def _create_workspace_and_profile(
    session: AsyncSession, slug: str, goals: list[str] | None = None
) -> tuple[Workspace, ContentProfile]:
    workspace = Workspace(name=slug, slug=f"{slug}-{uuid.uuid4().hex[:8]}")
    session.add(workspace)
    await session.flush()
    profile = ContentProfile(
        workspace_id=workspace.id,
        type=ContentProfileType.CREATOR,
        name="Test Creator",
        goals=goals or ["growth"],
    )
    session.add(profile)
    await session.flush()
    return workspace, profile


async def _get_or_create_market_intelligence(
    session: AsyncSession, profile: ContentProfile
) -> MarketIntelligence:
    result = await session.execute(
        select(MarketIntelligence).where(MarketIntelligence.content_profile_id == profile.id)
    )
    market = result.scalar_one_or_none()
    if market is None:
        market = MarketIntelligence(content_profile_id=profile.id, summary="Signals")
        session.add(market)
        await session.flush()
    return market


async def _create_market_signal(session: AsyncSession, profile: ContentProfile) -> MarketSignal:
    market = await _get_or_create_market_intelligence(session, profile)
    signal = MarketSignal(
        market_intelligence_id=market.id,
        title="High engagement format",
        velocity_score=1.0,
        engagement_score=1.0,
        relevance_score=1.0,
    )
    session.add(signal)
    await session.flush()
    return signal


async def _seed_current_synthesis(
    session: AsyncSession,
    profile: ContentProfile,
    *,
    generation_source: AnalysisGenerationSource = AnalysisGenerationSource.AI,
) -> ContentIntelligenceSynthesis:
    repository = ContentIntelligenceSynthesisRepository(session)
    synthesis = ContentIntelligenceSynthesis(
        profile_id=profile.id,
        summary="Short tactical explainer videos consistently outperform the baseline.",
        key_themes=["tactical explainers", "short-form retention"],
        supporting_analyses=[str(uuid.uuid4())],
        generation_source=generation_source,
        is_current=True,
        is_stale=False,
    )
    await repository.create(synthesis)
    await session.commit()
    return synthesis


def _fake_reasoning_router(*, failure: bool = False, captured: dict | None = None) -> AIRouter:
    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            if captured is not None:
                captured["user_prompt"] = kwargs["user_prompt"]
            if failure:
                raise AIProviderRequestError("provider unavailable")
            return OpportunityRationaleLLMResult(
                strategic_rationale=(
                    "Tactical explainer videos are working well for this audience, so this "
                    "signal is worth pursuing for the growth objective."
                )
            )

    providers = ProviderRegistry()
    providers.register("gemini", FakeProvider)
    models = ModelRegistry(
        [
            AIModelConfig(
                provider="gemini",
                model_name="fake-model",
                capabilities=frozenset({AICapability.STRUCTURED_OUTPUT, AICapability.REASONING}),
            )
        ]
    )
    return AIRouter(models, providers)


async def _create_opportunity(
    session: AsyncSession,
    workspace: Workspace,
    profile: ContentProfile,
    arq_pool,
):
    signal = await _create_market_signal(session, profile)
    service = ContentOpportunityService(session)
    opportunity = await service.create(
        profile.id,
        workspace.id,
        arq_pool,
        source_signal=OpportunitySource.TREND,
        market_signal_id=signal.id,
        title="Adapt the format",
        target_objective=TargetObjective.GROWTH,
        recommended_format="short_video",
    )
    return opportunity


async def test_opportunity_created_instantly_with_deterministic_placeholder(
    db_session: AsyncSession,
) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-instant")
    arq_pool = AsyncMock()

    opportunity = await _create_opportunity(db_session, workspace, profile, arq_pool)

    assert opportunity.strategic_rationale  # usable immediately, no blocking on AI
    assert opportunity.rationale_generation_source == RationaleGenerationSource.DETERMINISTIC
    assert opportunity.rationale_generated_at is None
    arq_pool.enqueue_job.assert_awaited_once()


async def test_async_reasoning_updates_rationale_grounded_in_synthesis(
    db_session: AsyncSession,
) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-grounded")
    await _seed_current_synthesis(db_session, profile)
    opportunity = await _create_opportunity(db_session, workspace, profile, AsyncMock())
    placeholder = opportunity.strategic_rationale
    score_components = opportunity.opportunity_metadata["score_components"]
    priority_before = opportunity.priority
    score_before = opportunity.opportunity_score

    captured: dict = {}
    router = _fake_reasoning_router(captured=captured)
    updated = await generate_rationale(db_session, opportunity.id, profile.id, router)

    assert updated.rationale_generation_source == RationaleGenerationSource.AI
    assert updated.strategic_rationale != placeholder
    assert updated.rationale_generated_at is not None
    # Grounded, not hallucinated: the exact synthesis summary and this
    # opportunity's real score components were part of what the reasoner saw.
    assert "Short tactical explainer videos" in captured["user_prompt"]
    assert str(score_components["signal_strength"]) in captured["user_prompt"]
    # Score/priority/ranking are byte-identical before and after reasoning.
    assert updated.opportunity_score == score_before
    assert updated.priority == priority_before


async def test_no_synthesis_yet_falls_back_to_deterministic(db_session: AsyncSession) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-no-synthesis")
    opportunity = await _create_opportunity(db_session, workspace, profile, AsyncMock())
    placeholder = opportunity.strategic_rationale

    router = _fake_reasoning_router()
    updated = await generate_rationale(db_session, opportunity.id, profile.id, router)

    assert updated.rationale_generation_source == RationaleGenerationSource.DETERMINISTIC
    assert updated.strategic_rationale == placeholder
    assert updated.rationale_generated_at is not None


async def test_ai_provider_failure_falls_back_to_deterministic(db_session: AsyncSession) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-ai-failure")
    await _seed_current_synthesis(db_session, profile)
    opportunity = await _create_opportunity(db_session, workspace, profile, AsyncMock())
    placeholder = opportunity.strategic_rationale

    router = _fake_reasoning_router(failure=True)
    updated = await generate_rationale(db_session, opportunity.id, profile.id, router)

    assert updated.rationale_generation_source == RationaleGenerationSource.DETERMINISTIC
    assert updated.strategic_rationale == placeholder


async def test_insufficient_data_synthesis_does_not_count_as_available(
    db_session: AsyncSession,
) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-insufficient")
    await _seed_current_synthesis(
        db_session, profile, generation_source=AnalysisGenerationSource.INSUFFICIENT_DATA
    )
    opportunity = await _create_opportunity(db_session, workspace, profile, AsyncMock())
    placeholder = opportunity.strategic_rationale

    router = _fake_reasoning_router()
    updated = await generate_rationale(db_session, opportunity.id, profile.id, router)

    assert updated.rationale_generation_source == RationaleGenerationSource.DETERMINISTIC
    assert updated.strategic_rationale == placeholder


async def test_bulk_creation_fans_out_independent_jobs_not_a_blocking_loop(
    db_session: AsyncSession,
) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-bulk")
    arq_pool = AsyncMock()

    opportunities = []
    for _ in range(3):
        opportunity = await _create_opportunity(db_session, workspace, profile, arq_pool)
        opportunities.append(opportunity)

    # One independent job per opportunity -- never a synchronous AI call
    # during creation, and never a single job covering multiple opportunities.
    assert arq_pool.enqueue_job.await_count == 3
    job_ids = {call.args[1] for call in arq_pool.enqueue_job.await_args_list}
    assert len(job_ids) == 3
    payloads = [call.args[2] for call in arq_pool.enqueue_job.await_args_list]
    opportunity_ids = {payload["opportunity_id"] for payload in payloads}
    assert opportunity_ids == {str(o.id) for o in opportunities}
    for opportunity in opportunities:
        assert opportunity.rationale_generation_source == RationaleGenerationSource.DETERMINISTIC


async def test_execute_ai_job_end_to_end_updates_rationale(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-e2e")
    await _seed_current_synthesis(db_session, profile)
    opportunity = await _create_opportunity(db_session, workspace, profile, AsyncMock())

    monkeypatch.setattr(
        "app.services.opportunity_reasoning.AIRouter", lambda: _fake_reasoning_router()
    )

    payload = {
        "opportunity_id": str(opportunity.id),
        "profile_id": str(profile.id),
        "workspace_id": str(workspace.id),
    }
    arq_pool = AsyncMock()
    job = await submit_job(db_session, arq_pool, "opportunity_reasoning", profile.id, payload)
    await db_session.commit()

    await execute_ai_job({"redis": arq_pool}, str(job.id), payload)

    await db_session.refresh(opportunity)
    assert opportunity.rationale_generation_source == RationaleGenerationSource.AI


async def test_rate_limit_defers_job_instead_of_dropping(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_reasoning_requests_per_window", 1)
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-ratelimit")
    await _seed_current_synthesis(db_session, profile)
    monkeypatch.setattr(
        "app.services.opportunity_reasoning.AIRouter", lambda: _fake_reasoning_router()
    )

    first = await _create_opportunity(db_session, workspace, profile, AsyncMock())
    second_signal = await _create_market_signal(db_session, profile)
    second = await ContentOpportunityService(db_session).create(
        profile.id,
        workspace.id,
        AsyncMock(),
        source_signal=OpportunitySource.TREND,
        market_signal_id=second_signal.id,
        title="Second opportunity",
        target_objective=TargetObjective.GROWTH,
    )

    arq_pool = AsyncMock()
    payload_1 = {
        "opportunity_id": str(first.id),
        "profile_id": str(profile.id),
        "workspace_id": str(workspace.id),
    }
    payload_2 = {
        "opportunity_id": str(second.id),
        "profile_id": str(profile.id),
        "workspace_id": str(workspace.id),
    }
    job_1 = await submit_job(db_session, arq_pool, "opportunity_reasoning", profile.id, payload_1)
    job_2 = await submit_job(db_session, arq_pool, "opportunity_reasoning", profile.id, payload_2)
    await db_session.commit()

    # First consumes the (window size 1) budget and completes normally.
    await execute_ai_job({"redis": arq_pool}, str(job_1.id), payload_1)
    await db_session.refresh(first)
    assert first.rationale_generation_source == RationaleGenerationSource.AI

    # Second is over budget: it must be requeued (deferred), not failed or
    # dropped -- the opportunity keeps its usable deterministic placeholder.
    await execute_ai_job({"redis": arq_pool}, str(job_2.id), payload_2)
    await db_session.refresh(second)
    assert second.rationale_generation_source == RationaleGenerationSource.DETERMINISTIC
    await db_session.refresh(job_2)
    assert job_2.status == JobStatus.QUEUED
    deferred_calls = [
        call
        for call in arq_pool.enqueue_job.await_args_list
        if "ratelimit" in call.kwargs.get("_job_id", "")
    ]
    assert len(deferred_calls) == 1
    assert deferred_calls[0].kwargs["_defer_by"] == settings.rate_limit_window_seconds


async def test_score_and_rank_unchanged_by_reasoning(db_session: AsyncSession) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "reasoning-score-stable")
    await _seed_current_synthesis(db_session, profile)
    opportunity = await _create_opportunity(db_session, workspace, profile, AsyncMock())

    before = {
        "opportunity_score": opportunity.opportunity_score,
        "relevance_score": opportunity.relevance_score,
        "priority": opportunity.priority,
        "opportunity_metadata": dict(opportunity.opportunity_metadata),
    }

    router = _fake_reasoning_router()
    updated = await generate_rationale(db_session, opportunity.id, profile.id, router)

    assert updated.opportunity_score == before["opportunity_score"]
    assert updated.relevance_score == before["relevance_score"]
    assert updated.priority == before["priority"]
    assert (
        updated.opportunity_metadata["score_components"]
        == before["opportunity_metadata"]["score_components"]
    )
