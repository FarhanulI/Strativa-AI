import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.strategy.opportunity_scorer import OpportunityScorer
from app.learning.extraction import extract_learnings_for_profile
from app.main import app
from app.models.content_opportunity import OpportunitySource, TargetObjective
from app.models.content_performance import ContentPerformance
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.learning import Learning, LearningDimension, LearningStatus
from app.models.market_intelligence import MarketIntelligence
from app.models.market_signal import MarketSignal
from app.models.performance_analysis import PerformanceAnalysis
from app.models.workspace import Workspace
from app.repositories.learning import LearningRepository
from app.services.ai.errors import AIProviderRequestError
from app.services.ai.registry import AIModelConfig, ModelRegistry, ProviderRegistry
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AICapability
from app.services.content_opportunity import ContentOpportunityService
from tests.conftest import authenticate_as_workspace_owner


def _fake_learning_router(*, failure: bool = False) -> AIRouter:
    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            if failure:
                raise AIProviderRequestError("provider unavailable")
            from app.schemas.learning import LearningExplanationLLMResult

            return LearningExplanationLLMResult(explanation="AI-authored explanation.")

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


async def _add_analyzed_record(
    session: AsyncSession,
    profile: ContentProfile,
    *,
    format: str,
    relative_engagement: float,
) -> ContentPerformance:
    record = ContentPerformance(profile_id=profile.id, platform="instagram", format=format)
    session.add(record)
    await session.flush()
    analysis = PerformanceAnalysis(
        profile_id=profile.id,
        content_performance_id=record.id,
        relative_engagement=relative_engagement,
        baseline_available=True,
        comparables_count=3,
    )
    session.add(analysis)
    await session.flush()
    record.analysis = analysis
    return record


# --- Scorer unit tests -------------------------------------------------


def test_learning_alignment_defaults_to_zero_and_preserves_total() -> None:
    scorer = OpportunityScorer()
    signal = type(
        "Signal",
        (),
        {
            "strength_score": 1.0,
            "topic": "football",
            "expires_at": None,
            "detected_at": None,
        },
    )()
    profile = type("Profile", (), {"topics": ["football"], "expertise": [], "goals": ["growth"]})()

    result = scorer.score(profile, signal, "growth")

    assert result.learning_alignment == 0.0
    assert result.total == 0.9


def test_learning_alignment_applies_capped_bonus_on_format_match() -> None:
    scorer = OpportunityScorer()
    signal = type(
        "Signal",
        (),
        {"strength_score": 1.0, "topic": "football", "expires_at": None, "detected_at": None},
    )()
    profile = type("Profile", (), {"topics": ["football"], "expertise": [], "goals": ["growth"]})()
    learning = Learning(
        profile_id=uuid.uuid4(),
        dimension=LearningDimension.FORMAT,
        dimension_value="short_video",
        pattern_description="short_video outperforms",
        confidence_level=0.8,
        supporting_evidence={},
        status=LearningStatus.ACTIVE,
    )

    result = scorer.score(
        profile, signal, "growth", recommended_format="short_video", learnings=[learning]
    )

    assert result.learning_alignment == pytest.approx(0.8 * OpportunityScorer.LEARNING_ALIGNMENT_WEIGHT)
    assert result.total == pytest.approx(0.9 + result.learning_alignment)


def test_learning_alignment_ignores_superseded_learnings() -> None:
    scorer = OpportunityScorer()
    learning = Learning(
        profile_id=uuid.uuid4(),
        dimension=LearningDimension.FORMAT,
        dimension_value="short_video",
        pattern_description="short_video outperforms",
        confidence_level=0.9,
        supporting_evidence={},
        status=LearningStatus.SUPERSEDED,
    )

    adjustment = scorer.calculate_learning_alignment("short_video", None, [learning])

    assert adjustment == 0.0


# --- Extraction determinism/idempotency --------------------------------


async def test_extraction_surfaces_high_performing_format_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    _, profile = await _create_workspace_and_profile(db_session, "learning-extraction")
    for _ in range(4):
        await _add_analyzed_record(db_session, profile, format="talking_head", relative_engagement=1.0)
    for _ in range(3):
        await _add_analyzed_record(
            db_session, profile, format="short_video", relative_engagement=2.0
        )
    await db_session.commit()

    router = _fake_learning_router()
    first_run = await extract_learnings_for_profile(db_session, profile.id, router)
    assert any(
        learning.dimension == LearningDimension.FORMAT
        and learning.dimension_value == "short_video"
        for learning in first_run
    )
    matched = next(
        learning for learning in first_run if learning.dimension_value == "short_video"
    )
    assert matched.explanation == "AI-authored explanation."

    repository = LearningRepository(db_session)
    all_learnings = await repository.list_by_profile(profile.id)
    count_after_first_run = len(all_learnings)

    second_run = await extract_learnings_for_profile(db_session, profile.id, router)
    assert second_run  # re-extraction still returns the (upserted) learning
    all_learnings_after_second_run = await repository.list_by_profile(profile.id)
    assert len(all_learnings_after_second_run) == count_after_first_run


async def test_extraction_falls_back_to_deterministic_explanation_on_ai_failure(
    db_session: AsyncSession,
) -> None:
    _, profile = await _create_workspace_and_profile(db_session, "learning-extraction-fallback")
    for _ in range(4):
        await _add_analyzed_record(db_session, profile, format="talking_head", relative_engagement=1.0)
    for _ in range(3):
        await _add_analyzed_record(
            db_session, profile, format="short_video", relative_engagement=2.0
        )
    await db_session.commit()

    router = _fake_learning_router(failure=True)
    learnings = await extract_learnings_for_profile(db_session, profile.id, router)

    matched = next(learning for learning in learnings if learning.dimension_value == "short_video")
    assert matched.explanation == matched.pattern_description
    from app.models.learning import ExplanationGenerationSource

    assert matched.explanation_generation_source == ExplanationGenerationSource.DETERMINISTIC


async def test_extraction_skips_profile_below_minimum_analyses(db_session: AsyncSession) -> None:
    _, profile = await _create_workspace_and_profile(db_session, "learning-extraction-too-few")
    await _add_analyzed_record(db_session, profile, format="short_video", relative_engagement=2.0)
    await db_session.commit()

    router = _fake_learning_router()
    learnings = await extract_learnings_for_profile(db_session, profile.id, router)

    assert learnings == []


# --- CRUD/list API with ownership chain --------------------------------


async def _seed_learning(session: AsyncSession, profile: ContentProfile) -> Learning:
    repository = LearningRepository(session)
    learning = Learning(
        profile_id=profile.id,
        dimension=LearningDimension.FORMAT,
        dimension_value="short_video",
        pattern_description="short_video outperforms",
        confidence_level=0.8,
        supporting_evidence={"sample_size": 3},
    )
    await repository.create(learning)
    await session.commit()
    return learning


async def test_learning_crud_and_list(override_get_db, db_session: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace, profile = await _create_workspace_and_profile(db_session, "learning-crud")
        await db_session.commit()
        await authenticate_as_workspace_owner(client, db_session, workspace.id)

        create_response = await client.post(
            f"/api/v1/profiles/{profile.id}/learnings",
            params={"workspace_id": str(workspace.id)},
            json={
                "dimension": "format",
                "dimension_value": "short_video",
                "pattern_description": "short_video outperforms",
                "confidence_level": 0.8,
                "supporting_evidence": {"sample_size": 3},
            },
        )
        assert create_response.status_code == 201, create_response.text
        learning_id = create_response.json()["id"]

        list_response = await client.get(
            f"/api/v1/profiles/{profile.id}/learnings",
            params={"workspace_id": str(workspace.id)},
        )
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        patch_response = await client.patch(
            f"/api/v1/profiles/{profile.id}/learnings/{learning_id}",
            params={"workspace_id": str(workspace.id)},
            json={"status": "superseded"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["status"] == "superseded"

        delete_response = await client.delete(
            f"/api/v1/profiles/{profile.id}/learnings/{learning_id}",
            params={"workspace_id": str(workspace.id)},
        )
        assert delete_response.status_code == 204


async def test_learning_cross_tenant_access_returns_404(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, profile = await _create_workspace_and_profile(db_session, "learning-owner")
        learning = await _seed_learning(db_session, profile)

        other_workspace, _ = await _create_workspace_and_profile(db_session, "learning-intruder")
        await db_session.commit()
        await authenticate_as_workspace_owner(client, db_session, other_workspace.id)

        response = await client.get(
            f"/api/v1/profiles/{profile.id}/learnings/{learning.id}",
            params={"workspace_id": str(other_workspace.id)},
        )
        assert response.status_code == 404


# --- Feedback loop closure: wiring into opportunity creation ------------


async def test_active_learning_influences_new_opportunity_score_and_metadata(
    db_session: AsyncSession,
) -> None:
    workspace, profile = await _create_workspace_and_profile(db_session, "learning-feedback-loop")
    learning = await _seed_learning(db_session, profile)

    market = MarketIntelligence(content_profile_id=profile.id, summary="Signals")
    db_session.add(market)
    await db_session.flush()
    signal = MarketSignal(
        market_intelligence_id=market.id,
        title="High engagement format",
        velocity_score=1.0,
        engagement_score=1.0,
        relevance_score=1.0,
    )
    db_session.add(signal)
    await db_session.flush()

    service = ContentOpportunityService(db_session)
    opportunity = await service.create(
        profile.id,
        workspace.id,
        AsyncMock(),
        source_signal=OpportunitySource.TREND,
        market_signal_id=signal.id,
        title="Adapt the format",
        target_objective=TargetObjective.GROWTH,
        recommended_format="short_video",
    )

    assert opportunity.opportunity_metadata["score_components"]["learning_alignment"] > 0
    assert opportunity.opportunity_metadata["influencing_learning_id"] == str(learning.id)


async def test_strategic_rationale_context_references_influencing_learning(
    db_session: AsyncSession,
) -> None:
    from app.models.content_intelligence_synthesis import ContentIntelligenceSynthesis
    from app.models.intelligence_analysis import AnalysisGenerationSource
    from app.repositories.content_intelligence_synthesis import (
        ContentIntelligenceSynthesisRepository,
    )
    from app.schemas.content_opportunity import OpportunityRationaleLLMResult
    from app.services.opportunity_reasoning import generate_rationale

    workspace, profile = await _create_workspace_and_profile(db_session, "learning-rationale")
    learning = await _seed_learning(db_session, profile)

    market = MarketIntelligence(content_profile_id=profile.id, summary="Signals")
    db_session.add(market)
    await db_session.flush()
    signal = MarketSignal(
        market_intelligence_id=market.id,
        title="High engagement format",
        velocity_score=1.0,
        engagement_score=1.0,
        relevance_score=1.0,
    )
    db_session.add(signal)
    await db_session.flush()

    synthesis_repository = ContentIntelligenceSynthesisRepository(db_session)
    await synthesis_repository.create(
        ContentIntelligenceSynthesis(
            profile_id=profile.id,
            summary="Short tactical videos outperform.",
            key_themes=["short-form"],
            supporting_analyses=[str(uuid.uuid4())],
            generation_source=AnalysisGenerationSource.AI,
            is_current=True,
            is_stale=False,
        )
    )
    await db_session.commit()

    service = ContentOpportunityService(db_session)
    opportunity = await service.create(
        profile.id,
        workspace.id,
        AsyncMock(),
        source_signal=OpportunitySource.TREND,
        market_signal_id=signal.id,
        title="Adapt the format",
        target_objective=TargetObjective.GROWTH,
        recommended_format="short_video",
    )

    captured: dict = {}

    class FakeProvider:
        provider = "gemini"

        async def generate_structured(self, **kwargs):
            captured["user_prompt"] = kwargs["user_prompt"]
            return OpportunityRationaleLLMResult(strategic_rationale="Grounded rationale.")

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
    router = AIRouter(models, providers)

    await generate_rationale(db_session, opportunity.id, profile.id, router)

    assert "influencing_learning" in captured["user_prompt"]
    assert learning.pattern_description in captured["user_prompt"]
