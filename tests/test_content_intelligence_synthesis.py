import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import fakeredis.aioredis as fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.content_intelligence.service import (
    ContentIntelligenceSynthesisService,
    generate_synthesis,
    synthesis_cache_key,
)
from app.infrastructure.jobs.pool import get_arq_pool
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.main import app
from app.models.audience_intelligence import AudienceIntelligence, PainPoint, Persona
from app.models.brand import Brand
from app.models.content_intelligence_synthesis import ContentIntelligenceSynthesis
from app.models.content_performance import ContentPerformance
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.intelligence_analysis import AnalysisGenerationSource
from app.models.market_intelligence import MarketIntelligence
from app.models.market_signal import MarketSignal
from app.models.performance_analysis import PerformanceAnalysis
from app.models.performance_insight import PerformanceInsight
from app.models.topic import Topic
from app.models.workspace import Workspace
from app.repositories.content_intelligence_synthesis import ContentIntelligenceSynthesisRepository
from app.schemas.content_intelligence_synthesis import ContentIntelligenceSynthesisLLMResult
from app.services.ai.errors import AIProviderRequestError
from app.services.ai.registry import AIModelConfig, ModelRegistry, ProviderRegistry
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AICapability
from app.services.intelligence_analysis import generate as generate_domain_analysis
from app.services.llm.performance_reasoner import PerformanceReasoner
from app.services.performance_insight import PerformanceInsightService


@pytest.fixture(autouse=True)
def _fake_cache_redis(monkeypatch: pytest.MonkeyPatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.api.v1.content_intelligence_synthesis.get_redis", lambda: fake)
    monkeypatch.setattr("app.content_intelligence.service.get_redis", lambda: fake)
    monkeypatch.setattr("app.api.v1.intelligence_analysis.get_redis", lambda: fake)
    monkeypatch.setattr("app.services.intelligence_analysis.get_redis", lambda: fake)
    yield fake


@pytest.fixture(autouse=True)
def _use_test_session_for_worker(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession):
    @asynccontextmanager
    async def _factory():
        yield db_session

    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.async_session_factory", _factory)
    monkeypatch.setattr("app.services.intelligence_analysis.async_session_factory", _factory)
    monkeypatch.setattr("app.content_intelligence.service.async_session_factory", _factory)


async def _create_profile(session: AsyncSession, slug: str) -> tuple[Workspace, ContentProfile]:
    workspace = Workspace(name=slug, slug=f"{slug}-{uuid.uuid4().hex[:8]}")
    session.add(workspace)
    await session.flush()
    profile = ContentProfile(
        workspace_id=workspace.id, type=ContentProfileType.CREATOR, name="Test Creator"
    )
    session.add(profile)
    await session.flush()
    return workspace, profile


async def _seed_brand(session: AsyncSession, profile: ContentProfile) -> Brand:
    brand = Brand(
        content_profile_id=profile.id,
        positioning="Affordable premium sportswear for young athletes",
    )
    session.add(brand)
    await session.flush()
    return brand


async def _seed_audience(session: AsyncSession, profile: ContentProfile) -> AudienceIntelligence:
    audience = AudienceIntelligence(content_profile_id=profile.id)
    session.add(audience)
    await session.flush()
    session.add(Persona(audience_intelligence_id=audience.id, name="Persona 1"))
    session.add(PainPoint(audience_intelligence_id=audience.id, title="Pain point 1"))
    await session.flush()
    await session.refresh(audience)
    return audience


async def _seed_market(session: AsyncSession, profile: ContentProfile) -> MarketIntelligence:
    market = MarketIntelligence(content_profile_id=profile.id)
    session.add(market)
    await session.flush()
    session.add(Topic(market_intelligence_id=market.id, name="Topic 1"))
    session.add(MarketSignal(market_intelligence_id=market.id, title="Signal 1"))
    await session.flush()
    await session.refresh(market)
    return market


async def _seed_active_performance_insight(
    session: AsyncSession, profile: ContentProfile
) -> PerformanceInsight:
    performance = ContentPerformance(profile_id=profile.id, platform="instagram", shares=10)
    session.add(performance)
    await session.flush()
    analysis = PerformanceAnalysis(profile_id=profile.id, content_performance_id=performance.id)
    session.add(analysis)
    await session.flush()
    insight = PerformanceInsight(
        profile_id=profile.id,
        performance_analysis_id=analysis.id,
        insight_type="winning_pattern",
        summary="Short tactical videos outperform the baseline.",
        likely_reason="Concise framing increases retention.",
        strategic_learning="Concise tactical explanations perform well.",
        recommended_action="Test another short tactical video.",
        confidence_score=0.8,
        model_provider="gemini",
        model_name="fake-model",
        prompt_version="performance_insight_v1",
        status="active",
    )
    session.add(insight)
    await session.flush()
    return insight


def _fake_domain_router(*, failure: bool = False) -> AIRouter:
    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            if failure:
                raise AIProviderRequestError("provider unavailable")
            from app.schemas.intelligence_analysis import (
                IntelligenceAnalysisLLMResult,
                IntelligenceInsightItem,
            )

            return IntelligenceAnalysisLLMResult(
                insights=[IntelligenceInsightItem(summary="Insight", rationale="Because data")]
            )

    providers = ProviderRegistry()
    providers.register("gemini", FakeProvider)
    models = ModelRegistry(
        [
            AIModelConfig(
                provider="gemini",
                model_name="fake-model",
                capabilities=frozenset({AICapability.STRUCTURED_OUTPUT}),
            )
        ]
    )
    return AIRouter(models, providers)


def _fake_synthesis_router(*, failure: bool = False) -> AIRouter:
    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            if failure:
                raise AIProviderRequestError("provider unavailable")
            return ContentIntelligenceSynthesisLLMResult(
                summary="Cross-domain synthesis summary.",
                key_themes=["consistency", "contrarian hooks"],
            )

    providers = ProviderRegistry()
    providers.register("gemini", FakeProvider)
    models = ModelRegistry(
        [
            AIModelConfig(
                provider="gemini",
                model_name="fake-model",
                capabilities=frozenset(
                    {
                        AICapability.STRUCTURED_OUTPUT,
                        AICapability.REASONING,
                        AICapability.LONG_CONTEXT,
                    }
                ),
            )
        ]
    )
    return AIRouter(models, providers)


async def _seed_all_four_domains(session: AsyncSession, profile: ContentProfile) -> None:
    await _seed_brand(session, profile)
    await _seed_audience(session, profile)
    await _seed_market(session, profile)
    await session.refresh(profile)
    await generate_domain_analysis(session, "brand", profile.id, _fake_domain_router())
    await generate_domain_analysis(session, "audience", profile.id, _fake_domain_router())
    await generate_domain_analysis(session, "market", profile.id, _fake_domain_router())
    await _seed_active_performance_insight(session, profile)
    await session.commit()


async def test_grounded_synthesis_across_all_four_inputs(db_session: AsyncSession) -> None:
    _, profile = await _create_profile(db_session, "synthesis-grounded")
    await _seed_all_four_domains(db_session, profile)

    synthesis = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())

    assert synthesis.generation_source == AnalysisGenerationSource.AI
    assert synthesis.summary == "Cross-domain synthesis summary."
    assert synthesis.key_themes == ["consistency", "contrarian hooks"]
    assert len(synthesis.supporting_analyses) == 4  # brand + audience + market + 1 insight
    for record_id in synthesis.supporting_analyses:
        uuid.UUID(record_id)


@pytest.mark.parametrize("component_count", [0, 1])
async def test_insufficient_data_fallback_with_fewer_than_two_components(
    db_session: AsyncSession, component_count: int
) -> None:
    _, profile = await _create_profile(db_session, f"synthesis-insufficient-{component_count}")
    if component_count == 1:
        await _seed_brand(db_session, profile)
        await db_session.refresh(profile)
        await generate_domain_analysis(db_session, "brand", profile.id, _fake_domain_router())
        await db_session.commit()

    synthesis = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())

    assert synthesis.generation_source == AnalysisGenerationSource.INSUFFICIENT_DATA
    assert synthesis.key_themes == []
    assert synthesis.is_current is True
    # Genuinely thin Brand/Audience/Market data is never cold start, even
    # though Performance is also absent here.
    assert synthesis.cold_start is False


async def _seed_three_domains_no_performance(
    session: AsyncSession, profile: ContentProfile
) -> None:
    await _seed_brand(session, profile)
    await _seed_audience(session, profile)
    await _seed_market(session, profile)
    await session.refresh(profile)
    await generate_domain_analysis(session, "brand", profile.id, _fake_domain_router())
    await generate_domain_analysis(session, "audience", profile.id, _fake_domain_router())
    await generate_domain_analysis(session, "market", profile.id, _fake_domain_router())
    await session.commit()


def _fake_activation_synthesis_router(prompts: list[str], *, failure: bool = False) -> AIRouter:
    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, *, system_prompt, **kwargs):
            prompts.append(system_prompt)
            if failure:
                raise AIProviderRequestError("provider unavailable")
            return ContentIntelligenceSynthesisLLMResult(
                summary=(
                    "This profile hasn't published anything yet, so here is what a "
                    "strong first piece of content should look like, grounded in "
                    "your stated positioning, audience, and current market opportunity."
                ),
                key_themes=["first content opportunity", "activation"],
            )

    providers = ProviderRegistry()
    providers.register("gemini", FakeProvider)
    models = ModelRegistry(
        [
            AIModelConfig(
                provider="gemini",
                model_name="fake-model",
                capabilities=frozenset(
                    {
                        AICapability.STRUCTURED_OUTPUT,
                        AICapability.REASONING,
                        AICapability.LONG_CONTEXT,
                    }
                ),
            )
        ]
    )
    return AIRouter(models, providers)


async def test_cold_start_synthesis_runs_as_full_ai_generation(db_session: AsyncSession) -> None:
    """Brand+Audience+Market present and grounded, zero PublishedContent /
    ContentPerformance: this must run as a full generation_source=ai call
    (never insufficient_data) and the summary must read as an activation
    recommendation, not a degraded/apologetic result."""
    _, profile = await _create_profile(db_session, "synthesis-cold-start")
    await _seed_three_domains_no_performance(db_session, profile)

    prompts: list[str] = []
    synthesis = await generate_synthesis(
        db_session, profile.id, _fake_activation_synthesis_router(prompts)
    )

    assert synthesis.generation_source == AnalysisGenerationSource.AI
    assert synthesis.cold_start is True
    assert len(synthesis.supporting_analyses) == 3  # brand + audience + market only
    summary_lower = synthesis.summary.lower()
    assert "first piece of content" in summary_lower or "first content" in summary_lower
    assert any("has not published any content yet" in p for p in prompts)


async def test_cold_start_becomes_false_after_first_publish(db_session: AsyncSession) -> None:
    _, profile = await _create_profile(db_session, "synthesis-cold-to-warm")
    await _seed_three_domains_no_performance(db_session, profile)

    cold = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    assert cold.cold_start is True
    assert cold.generation_source == AnalysisGenerationSource.AI

    await _seed_active_performance_insight(db_session, profile)
    await db_session.commit()

    warm = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    assert warm.cold_start is False
    assert warm.generation_source == AnalysisGenerationSource.AI
    assert len(warm.supporting_analyses) == 4  # brand + audience + market + performance insight


async def test_ai_provider_failure_falls_back(db_session: AsyncSession) -> None:
    _, profile = await _create_profile(db_session, "synthesis-aifail")
    await _seed_all_four_domains(db_session, profile)

    synthesis = await generate_synthesis(
        db_session, profile.id, _fake_synthesis_router(failure=True)
    )

    assert synthesis.generation_source == AnalysisGenerationSource.AI_FALLBACK
    assert synthesis.key_themes  # deterministic list of available domain names


async def test_staleness_trigger_on_brand_regeneration(db_session: AsyncSession) -> None:
    _, profile = await _create_profile(db_session, "synthesis-stale-brand")
    await _seed_all_four_domains(db_session, profile)
    synthesis = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    assert synthesis.is_stale is False

    await db_session.refresh(profile)
    profile.brand.mission = "A new mission statement"
    await db_session.flush()
    await db_session.refresh(profile)
    await generate_domain_analysis(db_session, "brand", profile.id, _fake_domain_router())

    repository = ContentIntelligenceSynthesisRepository(db_session)
    current = await repository.get_current(profile.id)
    assert current.id == synthesis.id
    assert current.is_stale is True


async def test_staleness_trigger_on_performance_insight_creation(
    db_session: AsyncSession,
) -> None:
    _, profile = await _create_profile(db_session, "synthesis-stale-performance")
    await _seed_all_four_domains(db_session, profile)
    synthesis = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    assert synthesis.is_stale is False

    performance = ContentPerformance(profile_id=profile.id, platform="instagram", shares=20)
    db_session.add(performance)
    await db_session.commit()

    reasoner = PerformanceReasoner(_fake_domain_router())

    class _FakePerformanceProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            from app.schemas.content_performance import PerformanceInsightLLMResult

            return PerformanceInsightLLMResult(
                insight_type="winning_pattern",
                summary="New insight",
                likely_reason="Because",
                strategic_learning="Learning",
                recommended_action="Test again",
                confidence_score=0.7,
            )

    reasoner.router.providers.register("gemini", _FakePerformanceProvider)
    service = PerformanceInsightService(db_session, reasoner)
    await service.create(profile.id, profile.workspace_id, performance.id)

    repository = ContentIntelligenceSynthesisRepository(db_session)
    current = await repository.get_current(profile.id)
    assert current.id == synthesis.id
    assert current.is_stale is True


async def test_regeneration_preserves_history(db_session: AsyncSession) -> None:
    _, profile = await _create_profile(db_session, "synthesis-history")
    await _seed_all_four_domains(db_session, profile)

    first = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    assert first.is_current is True

    second = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    await db_session.refresh(first)

    assert second.is_current is True
    assert first.is_current is False

    repository = ContentIntelligenceSynthesisRepository(db_session)
    current = await repository.get_current(profile.id)
    assert current.id == second.id

    all_rows = (
        await db_session.execute(
            ContentIntelligenceSynthesis.__table__.select().where(
                ContentIntelligenceSynthesis.profile_id == profile.id
            )
        )
    ).all()
    assert len(all_rows) == 2


async def test_get_or_enqueue_ownership_isolation(
    db_session: AsyncSession, override_get_db
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace = await client.post(
            "/api/v1/workspaces", json={"name": "owner", "slug": "synthesis-owner"}
        )
        profile = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace.json()["id"]},
            json={"type": "creator", "name": "Owner Creator"},
        )
        other = await client.post(
            "/api/v1/workspaces", json={"name": "other", "slug": "synthesis-other"}
        )

        app.dependency_overrides[get_arq_pool] = lambda: AsyncMock()
        try:
            response = await client.get(
                f"/api/v1/profiles/{profile.json()['id']}/synthesis",
                params={"workspace_id": other.json()["id"]},
            )
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)

        assert response.status_code == 404


async def test_get_endpoint_enqueues_when_missing_then_serves_fresh_from_cache(
    db_session: AsyncSession, override_get_db
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace = await client.post(
            "/api/v1/workspaces", json={"name": "get", "slug": "synthesis-get"}
        )
        workspace_id = workspace.json()["id"]
        profile = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Get Creator"},
        )
        profile_id = profile.json()["id"]
        profile_row = await db_session.get(ContentProfile, uuid.UUID(profile_id))
        await _seed_all_four_domains(db_session, profile_row)

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            pending = await client.get(
                f"/api/v1/profiles/{profile_id}/synthesis",
                params={"workspace_id": workspace_id},
            )
            assert pending.status_code == 202
            assert pending.json()["status"] == "pending"
            arq_pool.enqueue_job.assert_awaited_once()

            job_id = arq_pool.enqueue_job.await_args.args[1]
            enqueued_payload = arq_pool.enqueue_job.await_args.args[2]
            await execute_ai_job({"redis": arq_pool}, job_id, enqueued_payload)

            fresh = await client.get(
                f"/api/v1/profiles/{profile_id}/synthesis",
                params={"workspace_id": workspace_id},
            )
            assert fresh.status_code == 200, fresh.text
            data = fresh.json()
            assert data["generation_source"] in ("ai", "ai_fallback")
            assert data["is_current"] is True
            assert data["is_stale"] is False

            # Second read is served from cache without another enqueue.
            cached = await client.get(
                f"/api/v1/profiles/{profile_id}/synthesis",
                params={"workspace_id": workspace_id},
            )
            assert cached.status_code == 200
            arq_pool.enqueue_job.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)


async def test_job_success_invalidates_cache(db_session: AsyncSession, _fake_cache_redis) -> None:
    workspace, profile = await _create_profile(db_session, "synthesis-cache-invalidate")
    await _seed_all_four_domains(db_session, profile)

    key = synthesis_cache_key(profile.id, workspace.id)
    await _fake_cache_redis.set(key, '{"stale": true}')

    from app.infrastructure.jobs.service import submit_job

    payload = {"profile_id": str(profile.id), "workspace_id": str(workspace.id)}
    arq_pool = AsyncMock()
    job = await submit_job(db_session, arq_pool, "strategic_synthesis", profile.id, payload)
    await db_session.commit()

    await execute_ai_job({"redis": arq_pool}, str(job.id), payload)

    assert await _fake_cache_redis.get(key) is None


async def test_mark_stale_invalidates_cache(db_session: AsyncSession, _fake_cache_redis) -> None:
    workspace, profile = await _create_profile(db_session, "synthesis-mark-stale-cache")
    await _seed_all_four_domains(db_session, profile)
    await generate_synthesis(db_session, profile.id, _fake_synthesis_router())

    key = synthesis_cache_key(profile.id, workspace.id)
    await _fake_cache_redis.set(key, '{"fresh": true}')

    await db_session.refresh(profile)
    profile.brand.mission = "Updated mission"
    await db_session.flush()
    await db_session.refresh(profile)
    await generate_domain_analysis(db_session, "brand", profile.id, _fake_domain_router())

    assert await _fake_cache_redis.get(key) is None


async def test_service_get_or_enqueue_returns_current_when_not_stale(
    db_session: AsyncSession,
) -> None:
    workspace, profile = await _create_profile(db_session, "synthesis-service-fresh")
    await _seed_all_four_domains(db_session, profile)
    synthesis = await generate_synthesis(db_session, profile.id, _fake_synthesis_router())
    await db_session.commit()

    service = ContentIntelligenceSynthesisService(db_session)
    result = await service.get_or_enqueue(profile.id, workspace.id, AsyncMock())

    assert result.pending_job is None
    assert result.synthesis.id == synthesis.id
