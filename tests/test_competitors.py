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
        json={"summary": "Market"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_competitor(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-create")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
            json={
                "name": "Rival Creator",
                "platform": "instagram",
                "profile_url": "https://instagram.com/rival",
                "niche": "football comedy",
                "relevance_score": 0.9,
                "competitor_metadata": {"followers": 150000},
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Rival Creator"
    assert data["platform"] == "instagram"
    assert data["competitor_metadata"]["followers"] == 150000


async def test_list_competitors(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        for name in ["A", "B"]:
            await client.post(
                f"/api/v1/market-intelligence/{market_id}/competitors",
                params={"workspace_id": workspace_id},
                json={"name": name},
            )

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_competitor(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
            json={"name": "Comp"},
        )
        competitor_id = created.json()["id"]

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/competitors/{competitor_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Comp"


async def test_update_competitor(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-update")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
            json={"name": "Original"},
        )
        competitor_id = created.json()["id"]

        response = await client.patch(
            f"/api/v1/market-intelligence/{market_id}/competitors/{competitor_id}",
            params={"workspace_id": workspace_id},
            json={"name": "Updated"},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


async def test_delete_competitor(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-delete")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        created = await client.post(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
            json={"name": "Comp"},
        )
        competitor_id = created.json()["id"]

        response = await client.delete(
            f"/api/v1/market-intelligence/{market_id}/competitors/{competitor_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_competitor_relevance_score_validation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-score")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
            json={"name": "Bad", "relevance_score": -0.5},
        )

    assert response.status_code == 422


async def test_competitor_workspace_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "comp-iso-1")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace1_id))
        workspace2_id = await _create_workspace(client, "comp-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace1_id, profile_id)

        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace2_id))
        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404


async def test_competitor_cascade_on_market_intelligence_delete(
    override_get_db, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "comp-cascade")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Creator")
        market_id = await _create_market_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
            json={"name": "Comp"},
        )

        delete_response = await client.delete(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
        )
        assert delete_response.status_code == 204

        response = await client.get(
            f"/api/v1/market-intelligence/{market_id}/competitors",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 404
