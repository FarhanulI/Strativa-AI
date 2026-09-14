from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.ai.strategy.opportunity_scorer import OpportunityScorer
from app.main import app

# Every opportunity creation fans out one opportunity_reasoning job (see
# docs/development/day-18.md); tests/conftest.py's autouse
# `_default_arq_pool_override` fakes the arq pool for every test in this
# suite, so these CRUD/scoring tests don't need their own override.


async def create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post("/api/v1/workspaces", json={"name": slug, "slug": slug})
    assert response.status_code == 201
    return response.json()["id"]


async def create_profile(client: AsyncClient, workspace_id: str, name: str, goals=None) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": "creator", "name": name, "goals": goals},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def create_signal(client: AsyncClient, workspace_id: str, profile_id: str) -> str:
    market = await client.post(
        f"/api/v1/profiles/{profile_id}/market-intelligence",
        params={"workspace_id": workspace_id},
        json={"summary": "Signals"},
    )
    assert market.status_code == 201
    signal = await client.post(
        f"/api/v1/market-intelligence/{market.json()['id']}/signals",
        params={"workspace_id": workspace_id},
        json={
            "title": "High engagement format",
            "velocity_score": 1,
            "engagement_score": 1,
            "relevance_score": 1,
        },
    )
    assert signal.status_code == 201
    return signal.json()["id"]


def test_scorer_boundaries_and_priority() -> None:
    scorer = OpportunityScorer()
    profile = SimpleNamespace(goals=["growth"])
    signal = SimpleNamespace(
        velocity_score=1.0,
        engagement_score=1.0,
        relevance_score=1.0,
        expires_at=None,
        detected_at=datetime.now(UTC),
    )
    result = scorer.score(profile, signal, "growth")
    assert result.total == 0.9
    assert scorer.calculate_goal_alignment("sales", ["growth"]) == 0.5
    assert scorer.calculate_goal_alignment("growth", None) == 0.5
    assert scorer.calculate_timeliness(datetime.now(UTC) - timedelta(seconds=1)) == 0.0


async def test_create_get_update_delete_creator_opportunity(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "opportunity-crud")
        profile_id = await create_profile(client, workspace_id, "Creator")
        signal_id = await create_signal(client, workspace_id, profile_id)
        created = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities",
            params={"workspace_id": workspace_id},
            json={
                "source_signal": "trend",
                "market_signal_id": signal_id,
                "title": "Adapt it",
                "target_objective": "growth",
                "recommended_format": "short_video",
            },
        )
        assert created.status_code == 201
        data = created.json()
        assert data["opportunity_score"] == 0.8
        assert data["priority"] == "high"
        assert data["status"] == "draft"
        assert data["opportunity_metadata"]["scoring_version"] == "v1"
        opportunity_id = data["id"]
        fetched = await client.get(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}",
            params={"workspace_id": workspace_id},
        )
        assert fetched.status_code == 200
        updated = await client.patch(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}",
            params={"workspace_id": workspace_id},
            json={"title": "Updated", "status": "active"},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated"
        deleted = await client.delete(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}",
            params={"workspace_id": workspace_id},
        )
        assert deleted.status_code == 204


async def test_opportunity_filters_sort_and_cross_profile_signal_rejection(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "opportunity-filter")
        profile_a = await create_profile(client, workspace_id, "A", ["growth"])
        profile_b = await create_profile(client, workspace_id, "B")
        signal_b = await create_signal(client, workspace_id, profile_b)
        rejected = await client.post(
            f"/api/v1/profiles/{profile_a}/opportunities",
            params={"workspace_id": workspace_id},
            json={
                "source_signal": "market_conversation",
                "market_signal_id": signal_b,
                "title": "Invalid",
                "target_objective": "growth",
            },
        )
        assert rejected.status_code == 404
        audience_signal = await client.post(
            f"/api/v1/profiles/{profile_a}/audience-signals",
            params={"workspace_id": workspace_id},
            json={"question": "How does this work?", "intent": "learn"},
        )
        assert audience_signal.status_code == 201
        for source, objective, signal_key, signal_id in [
            ("trend", "growth", "market_signal_id", None),
            ("audience_question", "authority", "audience_signal_id", audience_signal.json()["id"]),
        ]:
            if source == "trend":
                signal_id = await create_signal(client, workspace_id, profile_a)
            response = await client.post(
                f"/api/v1/profiles/{profile_a}/opportunities",
                params={"workspace_id": workspace_id},
                json={
                    "source_signal": source,
                    signal_key: signal_id,
                    "title": source,
                    "target_objective": objective,
                },
            )
            assert response.status_code == 201
        listed = await client.get(
            f"/api/v1/profiles/{profile_a}/opportunities",
            params={"workspace_id": workspace_id, "source_signal": "trend", "sort": "asc"},
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        other_workspace = await create_workspace(client, "opportunity-isolation")
        hidden = await client.get(
            f"/api/v1/profiles/{profile_a}/opportunities", params={"workspace_id": other_workspace}
        )
        assert hidden.status_code == 404
