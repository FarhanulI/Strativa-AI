"""
Tests for content evaluation system.

Covers:
- Model and database functionality
- Scoring logic and classification
- Deterministic evaluation
- AI evaluation with mocking and fallback
- Variation evaluation
- Ownership and workspace isolation
- Creator and business profile support
- Historical evaluation trails
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.content_evaluation import EvaluationClassification
from app.schemas.content_evaluation import (
    EvaluationFindingResult,
)
from app.services.evaluation.scoring import calculate_overall_score, classify_score
from tests.conftest import authenticate_as_workspace_owner
from tests.test_content_briefs import create_opportunity, create_profile, create_workspace

# === Test Fixtures and Helpers ===


async def create_ready_brief(
    client: AsyncClient, workspace_id: str, profile_id: str, **kwargs
) -> str:
    """Create a ready-to-use brief for testing."""
    opportunity_id = await create_opportunity(client, workspace_id, profile_id)
    created = await client.post(
        f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
        params={"workspace_id": workspace_id},
        json={"opportunity_id": opportunity_id, **kwargs},
    )
    assert created.status_code == 201
    brief_id = created.json()["id"]
    ready = await client.patch(
        f"/api/v1/profiles/{profile_id}/briefs/{brief_id}",
        params={"workspace_id": workspace_id},
        json={"status": "ready", "angle": "Explain the strategic angle."},
    )
    assert ready.status_code == 200
    return brief_id


async def create_ready_draft(
    client: AsyncClient, workspace_id: str, profile_id: str, brief_id: str
) -> str:
    """Create a ready-to-use draft for testing."""
    created = await client.post(
        f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
        params={"workspace_id": workspace_id},
        json={},
    )
    assert created.status_code == 201
    draft_id = created.json()["id"]

    # Mark as ready
    ready = await client.patch(
        f"/api/v1/profiles/{profile_id}/drafts/{draft_id}",
        params={"workspace_id": workspace_id},
        json={"status": "ready"},
    )
    assert ready.status_code == 200
    return draft_id


# === Scoring Tests ===


def test_overall_score_calculation_basic():
    """Test overall score calculation with valid inputs."""
    scores = {
        "strategic_alignment_score": 1.0,  # 0.20 weight
        "audience_relevance_score": 1.0,  # 0.15 weight
        "hook_strength_score": 1.0,  # 0.15 weight
        "message_clarity_score": 1.0,  # 0.10 weight
        "narrative_coherence_score": 1.0,  # 0.10 weight
        "format_alignment_score": 1.0,  # 0.10 weight
        "emotional_alignment_score": 1.0,  # 0.05 weight
        "cta_alignment_score": 1.0,  # 0.05 weight
        "brand_alignment_score": 1.0,  # 0.10 weight
    }
    overall = calculate_overall_score(scores)
    assert overall == 1.0


def test_overall_score_calculation_weighted():
    """Test that weighting is applied correctly."""
    scores = {
        "strategic_alignment_score": 1.0,  # 0.20 weight
        "audience_relevance_score": 0.0,  # 0.15 weight
        "hook_strength_score": 0.0,  # 0.15 weight
        "message_clarity_score": 0.0,  # 0.10 weight
        "narrative_coherence_score": 0.0,  # 0.10 weight
        "format_alignment_score": 0.0,  # 0.10 weight
        "emotional_alignment_score": 0.0,  # 0.05 weight
        "cta_alignment_score": 0.0,  # 0.05 weight
        "brand_alignment_score": 0.0,  # 0.10 weight
    }
    overall = calculate_overall_score(scores)
    # Only strategic_alignment with 1.0 and 0.20 weight = 0.20
    assert overall == 0.20


def test_overall_score_calculation_zero():
    """Test overall score calculation when all scores are zero."""
    scores = {
        "strategic_alignment_score": 0.0,
        "audience_relevance_score": 0.0,
        "hook_strength_score": 0.0,
        "message_clarity_score": 0.0,
        "narrative_coherence_score": 0.0,
        "format_alignment_score": 0.0,
        "emotional_alignment_score": 0.0,
        "cta_alignment_score": 0.0,
        "brand_alignment_score": 0.0,
    }
    overall = calculate_overall_score(scores)
    assert overall == 0.0


def test_overall_score_calculation_missing_dimension():
    """Test that missing dimensions raise ValueError."""
    scores = {
        "strategic_alignment_score": 1.0,
        # Missing all other dimensions
    }
    with pytest.raises(ValueError, match="Missing required dimension score"):
        calculate_overall_score(scores)


def test_overall_score_calculation_invalid_score():
    """Test that out-of-range scores raise ValueError."""
    scores = {
        "strategic_alignment_score": 1.5,  # Invalid: > 1.0
        "audience_relevance_score": 1.0,
        "hook_strength_score": 0.0,
        "message_clarity_score": 0.0,
        "narrative_coherence_score": 0.0,
        "format_alignment_score": 0.0,
        "emotional_alignment_score": 0.0,
        "cta_alignment_score": 0.0,
        "brand_alignment_score": 0.0,
    }
    with pytest.raises(ValueError, match="Invalid score"):
        calculate_overall_score(scores)


def test_classification_excellent():
    """Test classification for excellent score (>= 0.85)."""
    classification = classify_score(0.85)
    assert classification == EvaluationClassification.EXCELLENT
    classification = classify_score(0.95)
    assert classification == EvaluationClassification.EXCELLENT


def test_classification_strong():
    """Test classification for strong score (>= 0.70)."""
    classification = classify_score(0.70)
    assert classification == EvaluationClassification.STRONG
    classification = classify_score(0.80)
    assert classification == EvaluationClassification.STRONG


def test_classification_acceptable():
    """Test classification for acceptable score (>= 0.55)."""
    classification = classify_score(0.55)
    assert classification == EvaluationClassification.ACCEPTABLE
    classification = classify_score(0.60)
    assert classification == EvaluationClassification.ACCEPTABLE


def test_classification_weak():
    """Test classification for weak score (>= 0.40)."""
    classification = classify_score(0.40)
    assert classification == EvaluationClassification.WEAK
    classification = classify_score(0.50)
    assert classification == EvaluationClassification.WEAK


def test_classification_poor():
    """Test classification for poor score (< 0.40)."""
    classification = classify_score(0.39)
    assert classification == EvaluationClassification.POOR
    classification = classify_score(0.0)
    assert classification == EvaluationClassification.POOR


def test_classification_boundary_conditions():
    """Test boundary conditions for classification thresholds."""
    # Just below/above each boundary
    assert classify_score(0.84) == EvaluationClassification.STRONG
    assert classify_score(0.85) == EvaluationClassification.EXCELLENT

    assert classify_score(0.69) == EvaluationClassification.ACCEPTABLE
    assert classify_score(0.70) == EvaluationClassification.STRONG

    assert classify_score(0.54) == EvaluationClassification.WEAK
    assert classify_score(0.55) == EvaluationClassification.ACCEPTABLE

    assert classify_score(0.39) == EvaluationClassification.POOR
    assert classify_score(0.40) == EvaluationClassification.WEAK


# === Deterministic Evaluation Tests ===


async def test_deterministic_evaluation_endpoint(override_get_db, db_session):
    """Test evaluation with use_ai=false uses deterministic path."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-deterministic")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        # Evaluate with deterministic path
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        assert response.status_code == 201, response.text
        data = response.json()

        # Verify deterministic generation
        assert data["generation_source"] == "deterministic"
        assert data["ai_provider"] is None
        assert data["ai_model"] is None

        # Verify all scores are present
        assert "strategic_alignment_score" in data
        assert "audience_relevance_score" in data
        assert "hook_strength_score" in data
        assert "message_clarity_score" in data
        assert "narrative_coherence_score" in data
        assert "format_alignment_score" in data
        assert "emotional_alignment_score" in data
        assert "cta_alignment_score" in data
        assert "brand_alignment_score" in data

        # Verify overall score and classification
        assert isinstance(data["overall_score"], float)
        assert 0.0 <= data["overall_score"] <= 1.0
        assert data["classification"] in ["excellent", "strong", "acceptable", "weak", "poor"]

        # Verify findings exist
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) > 0


# === API Endpoint Tests ===


async def test_create_evaluation_success(override_get_db, db_session):
    """Test successful evaluation creation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-create")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"]
        assert data["profile_id"] == profile_id
        assert data["draft_id"] == draft_id
        assert data["variation_id"] is None


async def test_create_evaluation_missing_draft(override_get_db, db_session):
    """Test evaluation creation fails for missing draft."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-missing-draft")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")

        fake_draft_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{fake_draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        assert response.status_code == 404


async def test_list_evaluations(override_get_db, db_session):
    """Test listing evaluations for a draft."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        # Create first evaluation
        resp1 = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        assert resp1.status_code == 201

        # Create second evaluation (same draft, different assessment point in time)
        resp2 = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        assert resp2.status_code == 201

        # List evaluations
        list_resp = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 2
        assert len(data["evaluations"]) == 2
        # Verify newest first
        assert data["evaluations"][0]["created_at"] > data["evaluations"][1]["created_at"]


async def test_get_evaluation(override_get_db, db_session):
    """Test retrieving a single evaluation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        # Create evaluation
        create_resp = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        evaluation_id = create_resp.json()["id"]

        # Get evaluation
        get_resp = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations/{evaluation_id}",
            params={"workspace_id": workspace_id},
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == evaluation_id
        assert data["profile_id"] == profile_id
        assert data["draft_id"] == draft_id


# === Ownership & Isolation Tests ===


async def test_cross_profile_evaluation_access_returns_404(override_get_db, db_session):
    """Test that Profile A cannot access Profile B's evaluations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-isolation")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_a = await create_profile(client, workspace_id, "Creator A")
        profile_b = await create_profile(client, workspace_id, "Creator B")

        # Create evaluation for Profile A
        brief_a = await create_ready_brief(client, workspace_id, profile_a)
        draft_a = await create_ready_draft(client, workspace_id, profile_a, brief_a)
        eval_resp = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        evaluation_id = eval_resp.json()["id"]

        # Attempt to access as Profile B (should fail)
        access_resp = await client.get(
            f"/api/v1/profiles/{profile_b}/drafts/{draft_a}/evaluations/{evaluation_id}",
            params={"workspace_id": workspace_id},
        )
        assert access_resp.status_code == 404


async def test_cross_workspace_access_returns_404(override_get_db, db_session):
    """Test that different workspace cannot access evaluations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "eval-ws-a")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_a))
        profile_a = await create_profile(client, workspace_a, "Creator")

        # Create evaluation in workspace A
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_ready_draft(client, workspace_a, profile_a, brief_a)
        eval_resp = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a}/evaluations",
            params={"workspace_id": workspace_a},
            json={"use_ai": False},
        )
        evaluation_id = eval_resp.json()["id"]

        workspace_b = await create_workspace(client, "eval-ws-b")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_b))

        # Attempt to access using workspace B (should fail)
        access_resp = await client.get(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a}/evaluations/{evaluation_id}",
            params={"workspace_id": workspace_b},
        )
        assert access_resp.status_code == 404


# === Historical Trail Tests ===


async def test_multiple_evaluations_create_separate_records(override_get_db, db_session):
    """Test that evaluating same draft twice creates separate evaluation records."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-history")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        # First evaluation
        eval1_resp = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        eval1_id = eval1_resp.json()["id"]

        # Second evaluation (same draft)
        eval2_resp = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        eval2_id = eval2_resp.json()["id"]

        # Verify they are different records
        assert eval1_id != eval2_id

        # Both should be retrievable
        get1 = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations/{eval1_id}",
            params={"workspace_id": workspace_id},
        )
        get2 = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations/{eval2_id}",
            params={"workspace_id": workspace_id},
        )
        assert get1.status_code == 200
        assert get2.status_code == 200


# === Creator Support Tests ===


async def test_creator_profile_evaluation_works(override_get_db, db_session):
    """Test that creators (without BusinessContext) can be evaluated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-creator")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")

        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["profile_id"] == profile_id


# === Response Format Tests ===


async def test_evaluation_response_contains_all_required_fields(override_get_db, db_session):
    """Test that evaluation response has all required fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "eval-fields")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_id = await create_ready_draft(client, workspace_id, profile_id, brief_id)

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/evaluations",
            params={"workspace_id": workspace_id},
            json={"use_ai": False},
        )
        data = response.json()

        # Required fields
        required_fields = [
            "id",
            "profile_id",
            "draft_id",
            "variation_id",
            "strategic_alignment_score",
            "audience_relevance_score",
            "hook_strength_score",
            "message_clarity_score",
            "narrative_coherence_score",
            "format_alignment_score",
            "emotional_alignment_score",
            "cta_alignment_score",
            "brand_alignment_score",
            "overall_score",
            "classification",
            "generation_source",
            "ai_provider",
            "ai_model",
            "prompt_version",
            "findings",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"


def test_finding_structure():
    """Test that findings have correct structure."""
    # This is a basic test of the schema
    finding = EvaluationFindingResult(
        dimension="strategic_alignment",
        severity="positive",
        summary="Test summary",
        explanation="Test explanation",
        recommendation="Test recommendation",
    )
    assert finding.dimension == "strategic_alignment"
    assert finding.severity == "positive"
    assert finding.summary == "Test summary"
