from httpx import ASGITransport, AsyncClient

from app.main import app


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


async def test_create_topic(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-create")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football", "relevance_score": 0.8},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "football"
    assert data["relevance_score"] == 0.8


async def test_list_topics(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-list")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        for name in ["football", "cricket"]:
            await client.post(
                f"/api/v1/market-intelligence/{market_id}/topics",
                params={"workspace_id": workspace_id},
                json={"name": name},
            )

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_topic(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-get")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football"},
        )
        topic_id = created.json()["id"]

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/topics/{topic_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "football"


async def test_update_topic(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-update")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football"},
        )
        topic_id = created.json()["id"]

        response = await client.patch(
            f"/api/v1/market-intelligence/{market_id}/topics/{topic_id}",
            params={"workspace_id": workspace_id},
            json={"description": "Football content"},
        )

    assert response.status_code == 200
    assert response.json()["description"] == "Football content"


async def test_delete_topic(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-delete")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football"},
        )
        topic_id = created.json()["id"]

        response = await client.delete(
            f"/api/v1/market-intelligence/{market_id}/topics/{topic_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_topic_relevance_score_validation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-score")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football", "relevance_score": 1.5},
        )

    assert response.status_code == 422


async def test_duplicate_topic_prevented(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-dup")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football"},
        )
        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football"},
        )

    assert response.status_code == 409


async def test_topic_workspace_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "topic-iso-1")
        workspace2_id = await _create_workspace(client, "topic-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace1_id, profile_id)

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404


async def test_topic_cascade_on_market_intelligence_delete(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "topic-cascade")
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
            json={"name": "football"},
        )

        delete_response = await client.delete(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
        )
        assert delete_response.status_code == 204

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/topics",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 404
