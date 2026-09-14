import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import fakeredis.aioredis as fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.jobs.pool import get_arq_pool
from app.infrastructure.jobs.service import submit_job
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.main import app
from app.models.ai_job import JobStatus
from app.models.audience_intelligence import AudienceIntelligence, PainPoint, Persona
from app.models.brand import Brand
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.intelligence_analysis import AnalysisGenerationSource, GroundingBasis
from app.models.market_intelligence import MarketIntelligence
from app.models.market_signal import MarketSignal
from app.models.topic import Topic
from app.models.workspace import Workspace
from app.repositories.ai_job import AIJobRepository
from app.repositories.intelligence_analysis import IntelligenceAnalysisRepository
from app.schemas.intelligence_analysis import IntelligenceAnalysisLLMResult, IntelligenceInsightItem
from app.services.ai.errors import AIProviderRequestError
from app.services.ai.registry import AIModelConfig, ModelRegistry, ProviderRegistry
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AICapability
from app.services.intelligence_analysis import DOMAIN_CONFIGS, generate


@pytest.fixture(autouse=True)
def _fake_cache_redis(monkeypatch: pytest.MonkeyPatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.api.v1.intelligence_analysis.get_redis", lambda: fake)
    monkeypatch.setattr("app.services.intelligence_analysis.get_redis", lambda: fake)
    monkeypatch.setattr("app.content_intelligence.service.get_redis", lambda: fake)
    yield fake


@pytest.fixture(autouse=True)
def _use_test_session_for_worker(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession):
    @asynccontextmanager
    async def _factory():
        yield db_session

    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.async_session_factory", _factory)
    monkeypatch.setattr("app.services.intelligence_analysis.async_session_factory", _factory)


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


async def _seed_brand(session: AsyncSession, profile: ContentProfile, filled: bool) -> Brand:
    brand = Brand(
        content_profile_id=profile.id,
        positioning="Affordable premium sportswear for young athletes" if filled else None,
    )
    session.add(brand)
    await session.flush()
    return brand


async def _seed_audience(
    session: AsyncSession, profile: ContentProfile, personas: int, pain_points: int
) -> AudienceIntelligence:
    audience = AudienceIntelligence(content_profile_id=profile.id)
    session.add(audience)
    await session.flush()
    for i in range(personas):
        session.add(Persona(audience_intelligence_id=audience.id, name=f"Persona {i}"))
    for i in range(pain_points):
        session.add(PainPoint(audience_intelligence_id=audience.id, title=f"Pain point {i}"))
    await session.flush()
    await session.refresh(audience)
    return audience


async def _seed_market(
    session: AsyncSession, profile: ContentProfile, topics: int, signals: int
) -> MarketIntelligence:
    market = MarketIntelligence(content_profile_id=profile.id)
    session.add(market)
    await session.flush()
    for i in range(topics):
        session.add(Topic(market_intelligence_id=market.id, name=f"Topic {i}"))
    for i in range(signals):
        session.add(MarketSignal(market_intelligence_id=market.id, title=f"Signal {i}"))
    await session.flush()
    await session.refresh(market)
    return market


def _fake_router(*, failure: bool = False) -> AIRouter:
    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            if failure:
                raise AIProviderRequestError("provider unavailable")
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


# --- Shared parameterized harness: insufficient data & ownership isolation ---

DOMAINS = ["brand", "audience", "market"]


async def _seed_insufficient(session: AsyncSession, domain: str, profile: ContentProfile) -> None:
    if domain == "brand":
        await _seed_brand(session, profile, filled=False)
    elif domain == "audience":
        await _seed_audience(session, profile, personas=1, pain_points=0)
    elif domain == "market":
        await _seed_market(session, profile, topics=1, signals=0)


async def _seed_sufficient(session: AsyncSession, domain: str, profile: ContentProfile) -> None:
    if domain == "brand":
        await _seed_brand(session, profile, filled=True)
    elif domain == "audience":
        await _seed_audience(session, profile, personas=1, pain_points=1)
    elif domain == "market":
        await _seed_market(session, profile, topics=1, signals=1)


@pytest.mark.parametrize("domain", DOMAINS)
async def test_insufficient_data_fallback(db_session: AsyncSession, domain: str) -> None:
    _, profile = await _create_profile(db_session, f"insufficient-{domain}")
    await _seed_insufficient(db_session, domain, profile)
    await db_session.refresh(profile)

    analysis = await generate(db_session, domain, profile.id, _fake_router())

    assert analysis.generation_source == AnalysisGenerationSource.INSUFFICIENT_DATA
    assert analysis.insights[0]["rationale"] == "insufficient_data"
    assert analysis.is_current is True


@pytest.mark.parametrize("domain", DOMAINS)
async def test_grounded_generation_references_real_ids(
    db_session: AsyncSession, domain: str
) -> None:
    _, profile = await _create_profile(db_session, f"grounded-{domain}")
    await _seed_sufficient(db_session, domain, profile)
    await db_session.refresh(profile)

    analysis = await generate(db_session, domain, profile.id, _fake_router())

    assert analysis.generation_source == AnalysisGenerationSource.AI
    assert analysis.insights == [{"summary": "Insight", "rationale": "Because data"}]
    assert len(analysis.grounded_on) >= 1
    # Every id referenced must be a real record id that exists in the domain
    # (a root record or one of its children) — never fabricated by the LLM.
    for record_id in analysis.grounded_on:
        uuid.UUID(record_id)


@pytest.mark.parametrize("domain", ["audience", "market"])
async def test_stated_only_grounding_for_new_profile(db_session: AsyncSession, domain: str) -> None:
    """A brand-new profile with zero signal history (no personas/pain points,
    no topics/market signals) but onboarding-stated profile data must still
    be able to generate — never fall back to insufficient_data just because
    live signal data hasn't accumulated yet."""
    _, profile = await _create_profile(db_session, f"stated-only-{domain}")
    if domain == "audience":
        profile.description = "Football tactics explained simply for casual fans."
        profile.goals = ["grow to 50k engaged followers"]
    else:
        profile.topics = ["football tactics", "match analysis"]
        profile.expertise = ["tactical breakdowns"]
        profile.positioning = "The commentator who makes tactics simple"
    await db_session.flush()
    await db_session.refresh(profile)

    analysis = await generate(db_session, domain, profile.id, _fake_router())

    assert analysis.generation_source == AnalysisGenerationSource.AI
    assert analysis.grounding_basis == GroundingBasis.STATED
    assert any(entry.startswith("stated:") for entry in analysis.grounded_on)


@pytest.mark.parametrize("domain", DOMAINS)
async def test_ai_provider_failure_falls_back(db_session: AsyncSession, domain: str) -> None:
    _, profile = await _create_profile(db_session, f"aifail-{domain}")
    await _seed_sufficient(db_session, domain, profile)
    await db_session.refresh(profile)

    analysis = await generate(db_session, domain, profile.id, _fake_router(failure=True))

    assert analysis.generation_source == AnalysisGenerationSource.AI_FALLBACK
    assert analysis.insights[0]["rationale"] == "ai_provider_unavailable"


@pytest.mark.parametrize("domain", DOMAINS)
async def test_regeneration_on_material_data_change(db_session: AsyncSession, domain: str) -> None:
    _, profile = await _create_profile(db_session, f"regen-{domain}")
    await _seed_sufficient(db_session, domain, profile)
    await db_session.refresh(profile)

    first = await generate(db_session, domain, profile.id, _fake_router())
    first_fingerprint = first.source_fingerprint

    await db_session.refresh(profile)
    if domain == "brand":
        profile.brand.mission = "A new mission statement"
    elif domain == "audience":
        db_session.add(
            Persona(audience_intelligence_id=profile.audience_intelligence.id, name="New Persona")
        )
    else:
        db_session.add(
            Topic(market_intelligence_id=profile.market_intelligence.id, name="New Topic")
        )
    await db_session.flush()
    await db_session.refresh(profile)

    config = DOMAIN_CONFIGS[domain]
    grounding = config.grounding_fn(profile)
    assert grounding.fingerprint != first_fingerprint


@pytest.mark.parametrize("domain", DOMAINS)
async def test_get_or_enqueue_ownership_isolation(
    db_session: AsyncSession, domain: str, override_get_db
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace = await client.post(
            "/api/v1/workspaces", json={"name": "owner", "slug": f"owner-{domain}"}
        )
        profile = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace.json()["id"]},
            json={"type": "creator", "name": "Owner Creator"},
        )
        other = await client.post(
            "/api/v1/workspaces", json={"name": "other", "slug": f"other-{domain}"}
        )

        app.dependency_overrides[get_arq_pool] = lambda: AsyncMock()
        try:
            response = await client.get(
                f"/api/v1/profiles/{profile.json()['id']}/{domain}-analysis",
                params={"workspace_id": other.json()["id"]},
            )
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)

        assert response.status_code == 404


@pytest.mark.parametrize("domain", DOMAINS)
async def test_get_endpoint_enqueues_when_missing_then_serves_fresh_from_cache(
    db_session: AsyncSession, domain: str, override_get_db
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace = await client.post(
            "/api/v1/workspaces", json={"name": "get", "slug": f"get-{domain}"}
        )
        workspace_id = workspace.json()["id"]
        profile = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Get Creator"},
        )
        profile_id = profile.json()["id"]
        profile_row = await db_session.get(ContentProfile, uuid.UUID(profile_id))
        await _seed_sufficient(db_session, domain, profile_row)
        await db_session.refresh(profile_row)
        await db_session.commit()

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            pending = await client.get(
                f"/api/v1/profiles/{profile_id}/{domain}-analysis",
                params={"workspace_id": workspace_id},
            )
            assert pending.status_code == 202
            assert pending.json()["status"] == "pending"
            arq_pool.enqueue_job.assert_awaited_once()

            job_id = arq_pool.enqueue_job.await_args.args[1]
            enqueued_payload = arq_pool.enqueue_job.await_args.args[2]
            await execute_ai_job({"redis": arq_pool}, job_id, enqueued_payload)

            fresh = await client.get(
                f"/api/v1/profiles/{profile_id}/{domain}-analysis",
                params={"workspace_id": workspace_id},
            )
            assert fresh.status_code == 200, fresh.text
            data = fresh.json()
            assert data["generation_source"] in ("ai", "ai_fallback")
            assert data["is_current"] is True
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)


async def test_cache_hit_never_bypasses_ownership_check(
    db_session: AsyncSession, override_get_db
) -> None:
    """A cached analysis for the owning workspace must never be servable to
    a different workspace_id supplied for the same profile_id — the cache
    key is namespaced by workspace_id specifically to prevent this."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_workspace = await client.post(
            "/api/v1/workspaces", json={"name": "owner", "slug": "cache-leak-owner"}
        )
        owner_workspace_id = owner_workspace.json()["id"]
        profile = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": owner_workspace_id},
            json={"type": "creator", "name": "Owner Creator"},
        )
        profile_id = profile.json()["id"]
        profile_row = await db_session.get(ContentProfile, uuid.UUID(profile_id))
        await _seed_sufficient(db_session, "brand", profile_row)
        await db_session.refresh(profile_row)
        await db_session.commit()

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            pending = await client.get(
                f"/api/v1/profiles/{profile_id}/brand-analysis",
                params={"workspace_id": owner_workspace_id},
            )
            assert pending.status_code == 202
            job_id = arq_pool.enqueue_job.await_args.args[1]
            enqueued_payload = arq_pool.enqueue_job.await_args.args[2]
            await execute_ai_job({"redis": arq_pool}, job_id, enqueued_payload)

            owner_read = await client.get(
                f"/api/v1/profiles/{profile_id}/brand-analysis",
                params={"workspace_id": owner_workspace_id},
            )
            assert owner_read.status_code == 200

            attacker_workspace = await client.post(
                "/api/v1/workspaces", json={"name": "attacker", "slug": "cache-leak-attacker"}
            )
            attacker_read = await client.get(
                f"/api/v1/profiles/{profile_id}/brand-analysis",
                params={"workspace_id": attacker_workspace.json()["id"]},
            )
            assert attacker_read.status_code == 404
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)


async def test_job_success_invalidates_cache(db_session: AsyncSession, _fake_cache_redis) -> None:
    workspace, profile = await _create_profile(db_session, "cache-invalidate")
    await _seed_sufficient(db_session, "brand", profile)
    await db_session.refresh(profile)
    await db_session.commit()

    key = f"profile:{profile.id}:brand-analysis:workspace:{workspace.id}"
    await _fake_cache_redis.set(key, '{"stale": true}')

    payload = {"profile_id": str(profile.id), "workspace_id": str(workspace.id)}
    arq_pool = AsyncMock()
    job = await submit_job(db_session, arq_pool, "brand_analysis", profile.id, payload)
    await db_session.commit()

    await execute_ai_job({"redis": arq_pool}, str(job.id), payload)

    repository = AIJobRepository(db_session)
    refreshed = await repository.get_by_id(job.id)
    assert refreshed.status == JobStatus.SUCCEEDED
    assert await _fake_cache_redis.get(key) is None


async def test_is_current_flag_moves_to_newest_analysis(db_session: AsyncSession) -> None:
    _, profile = await _create_profile(db_session, "is-current")
    await _seed_sufficient(db_session, "brand", profile)
    await db_session.refresh(profile)

    first = await generate(db_session, "brand", profile.id, _fake_router())
    assert first.is_current is True

    profile.brand.mission = "Updated mission"
    await db_session.flush()
    await db_session.refresh(profile)

    second = await generate(db_session, "brand", profile.id, _fake_router())
    await db_session.refresh(first)

    assert second.is_current is True
    assert first.is_current is False

    repository = IntelligenceAnalysisRepository(db_session, DOMAIN_CONFIGS["brand"].model)
    current = await repository.get_current(profile.id)
    assert current.id == second.id
