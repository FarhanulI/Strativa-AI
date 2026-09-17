import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import authenticate_as_workspace_owner


async def _create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Workspace {slug}", "slug": slug},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_profile(client: AsyncClient, workspace_id: str, name: str) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": "creator", "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_market_intelligence(
    client: AsyncClient, workspace_id: str, profile_id: str
) -> str:
    response = await client.post(
        f"/api/v1/profiles/{profile_id}/market-intelligence",
        params={"workspace_id": workspace_id},
        json={"summary": "Market summary"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_topic(client: AsyncClient, workspace_id: str, market_id: str, name: str) -> str:
    response = await client.post(
        f"/api/v1/market-intelligence/{market_id}/topics",
        params={"workspace_id": workspace_id},
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_market_signal(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-create")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={
                "title": "Football transfer reaction videos surging",
                "source_type": "social",
                "signal_type": "trend",
                "velocity_score": 0.7,
                "relevance_score": 0.9,
                "engagement_score": 0.8,
                "signal_metadata": {"platform": "instagram", "hashtags": ["#football"]},
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Football transfer reaction videos surging"
    assert data["status"] == "active"
    assert data["signal_metadata"]["platform"] == "instagram"


async def test_list_market_signals(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        for title in ["A", "B"]:
            await client.post(
                f"/api/v1/market-intelligence/{market_id}/signals",
                params={"workspace_id": workspace_id},
                json={"title": title},
            )

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_market_signal(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Signal A"},
        )
        signal_id = created.json()["id"]

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals/{signal_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Signal A"


async def test_update_market_signal(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-update")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Original"},
        )
        signal_id = created.json()["id"]

        response = await client.patch(
            f"/api/v1/market-intelligence/{market_id}/signals/{signal_id}",
            params={"workspace_id": workspace_id},
            json={"title": "Updated", "status": "archived"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert response.json()["status"] == "archived"


async def test_delete_market_signal(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-delete")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "To delete"},
        )
        signal_id = created.json()["id"]

        response = await client.delete(
            f"/api/v1/market-intelligence/{market_id}/signals/{signal_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_filter_signals_by_status(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-filter-status")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Active", "status": "active"},
        )
        await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Archived", "status": "archived"},
        )

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id, "status": "archived"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "archived"


async def test_filter_signals_by_signal_type(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-filter-type")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        for signal_type, title in [("trend", "T"), ("event", "E")]:
            await client.post(
                f"/api/v1/market-intelligence/{market_id}/signals",
                params={"workspace_id": workspace_id},
                json={"title": title, "signal_type": signal_type},
            )

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id, "signal_type": "trend"},
        )

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_filter_signals_by_topic_id(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-filter-topic")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        topic_id = await _create_topic(client, workspace_id, market_id, "football")

        await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "With topic", "topic_id": topic_id},
        )
        await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Without topic"},
        )

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id, "topic_id": topic_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["topic_id"] == topic_id


async def test_signal_score_validation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-score")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Bad", "velocity_score": 2.0},
        )

    assert response.status_code == 422


async def test_invalid_topic_ownership_rejected(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-topic-ownership")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_a_id = await _create_profile(client, workspace_id, "Creator A")
        profile_b_id = await _create_profile(client, workspace_id, "Creator B")
        market_a_id = await _create_market_intelligence(client, workspace_id, profile_a_id)
        market_b_id = await _create_market_intelligence(client, workspace_id, profile_b_id)

        topic_b_id = await _create_topic(client, workspace_id, market_b_id, "cricket")

        response = await client.post(
            f"/api/v1/market-intelligence/{market_a_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Cross topic", "topic_id": topic_b_id},
        )

    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"].lower()


async def test_signal_workspace_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "signal-iso-1")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace1_id))
        workspace2_id = await _create_workspace(client, "signal-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace1_id, profile_id)

        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace2_id))
        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404


async def test_topic_deletion_sets_signal_topic_id_null(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-topic-null")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)
        topic_id = await _create_topic(client, workspace_id, market_id, "football")

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Signal with topic", "topic_id": topic_id},
        )
        signal_id = created.json()["id"]

        delete_response = await client.delete(
            f"/api/v1/market-intelligence/{market_id}/topics/{topic_id}",
            params={"workspace_id": workspace_id},
        )
        assert delete_response.status_code == 204

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals/{signal_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["topic_id"] is None


async def test_signal_cascade_on_market_intelligence_delete(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "signal-cascade")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
            json={"title": "Signal"},
        )

        delete_response = await client.delete(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
        )
        assert delete_response.status_code == 204

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/signals",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 404
