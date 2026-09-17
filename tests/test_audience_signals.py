import uuid
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from app.ai.strategy.opportunity_scorer import OpportunityScorer
from app.main import app
from tests.conftest import authenticate_as_workspace_owner


async def create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post("/api/v1/workspaces", json={"name": slug, "slug": slug})
    assert response.status_code == 201
    return response.json()["id"]


async def create_profile(client: AsyncClient, workspace_id: str, name: str, topics=None) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": "creator", "name": name, "topics": topics},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def create_signal(client: AsyncClient, workspace_id: str, profile_id: str, **values) -> dict:
    response = await client.post(
        f"/api/v1/profiles/{profile_id}/audience-signals",
        params={"workspace_id": workspace_id},
        json={"question": "How can I improve?", "intent": "learn", **values},
    )
    assert response.status_code == 201
    return response.json()


async def test_audience_signal_crud_and_filters(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "audience-signal-crud")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        first = await create_signal(
            client, workspace_id, profile_id, topic="photography", strength_score=0.3
        )
        second = await create_signal(
            client, workspace_id, profile_id, intent="solve", strength_score=0.9, status="resolved"
        )
        listed = await client.get(
            f"/api/v1/profiles/{profile_id}/audience-signals",
            params={
                "workspace_id": workspace_id,
                "status": "resolved",
                "sort_by": "strength_score",
            },
        )
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [second["id"]]
        fetched = await client.get(
            f"/api/v1/profiles/{profile_id}/audience-signals/{first['id']}",
            params={"workspace_id": workspace_id},
        )
        assert fetched.status_code == 200
        updated = await client.patch(
            f"/api/v1/profiles/{profile_id}/audience-signals/{first['id']}",
            params={"workspace_id": workspace_id},
            json={"question": "Updated question", "status": "archived"},
        )
        assert updated.status_code == 200
        deleted = await client.delete(
            f"/api/v1/profiles/{profile_id}/audience-signals/{first['id']}",
            params={"workspace_id": workspace_id},
        )
        assert deleted.status_code == 204


async def test_audience_signal_validation_and_workspace_isolation(
    override_get_db, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "audience-signal-a")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_a))
        profile_a = await create_profile(client, workspace_a, "A")
        signal = await create_signal(client, workspace_a, profile_a)
        invalid_score = await client.post(
            f"/api/v1/profiles/{profile_a}/audience-signals",
            params={"workspace_id": workspace_a},
            json={"question": "Bad", "intent": "learn", "strength_score": 1.1},
        )
        invalid_intent = await client.post(
            f"/api/v1/profiles/{profile_a}/audience-signals",
            params={"workspace_id": workspace_a},
            json={"question": "Bad", "intent": "unknown"},
        )

        workspace_b = await create_workspace(client, "audience-signal-b")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_b))
        profile_b = await create_profile(client, workspace_b, "B")
        hidden = await client.get(
            f"/api/v1/profiles/{profile_a}/audience-signals/{signal['id']}",
            params={"workspace_id": workspace_b},
        )
        profile_hidden = await client.get(
            f"/api/v1/profiles/{profile_b}/audience-signals/{signal['id']}",
            params={"workspace_id": workspace_b},
        )

    assert invalid_score.status_code == 422
    assert invalid_intent.status_code == 422
    assert hidden.status_code == 404
    assert profile_hidden.status_code == 404


def test_audience_signal_scorer_uses_strength_and_topic() -> None:
    scorer = OpportunityScorer()
    profile = type(
        "Profile",
        (),
        {"goals": ["authority"], "topics": ["photography"], "expertise": []},
    )()
    signal = type(
        "Signal",
        (),
        {
            "strength_score": 1.0,
            "topic": "photography",
            "expires_at": None,
            "observed_at": datetime.now(UTC),
        },
    )()
    result = scorer.score(profile, signal, "authority")
    assert result.signal_strength == 1.0
    assert result.profile_relevance == 1.0
    assert result.total == 0.9


async def test_audience_signal_creates_opportunity(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "audience-opportunity")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Photographer", ["photography"])
        signal = await create_signal(
            client, workspace_id, profile_id, topic="photography", strength_score=1.0
        )
        opportunity = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities",
            params={"workspace_id": workspace_id},
            json={
                "source_signal": "audience_question",
                "audience_signal_id": signal["id"],
                "title": "Answer the audience",
                "target_objective": "authority",
                "recommended_format": "carousel",
            },
        )
        missing_signal = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities",
            params={"workspace_id": workspace_id},
            json={
                "source_signal": "audience_question",
                "title": "Missing",
                "target_objective": "growth",
            },
        )

    assert opportunity.status_code == 201
    data = opportunity.json()
    assert data["audience_signal_id"] == signal["id"]
    assert data["market_signal_id"] is None
    assert data["opportunity_metadata"]["score_components"]["signal_strength"] == 1.0
    assert "How can I improve?" in data["strategic_rationale"]
    assert missing_signal.status_code == 404
