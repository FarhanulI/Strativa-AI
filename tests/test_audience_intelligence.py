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


async def test_create_audience_intelligence(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "audience-create")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={
                "summary": "Young social media users",
                "language": "Bangla",
                "geography": "Bangladesh",
                "demographics": {"age_range": "18-30"},
                "psychographics": {"interests": ["memes", "comedy"]},
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["summary"] == "Young social media users"
    assert data["language"] == "Bangla"
    assert data["geography"] == "Bangladesh"


async def test_get_audience_intelligence(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "audience-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Young audience"},
        )

        response = await client.get(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Young audience"


async def test_update_audience_intelligence(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "audience-update")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Original summary"},
        )

        response = await client.patch(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Updated summary"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Updated summary"


async def test_delete_audience_intelligence(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "audience-delete")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "To delete"},
        )

        response = await client.delete(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_duplicate_audience_intelligence_returns_409(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "audience-duplicate")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "First"},
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Second"},
        )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


async def test_creator_can_create_audience_intelligence(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "audience-creator")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Funny Rahim")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace_id},
            json={
                "summary": "Young relatable comedy viewers",
                "language": "Bangla",
                "geography": "Bangladesh",
                "demographics": {"age_range": "18-25"},
            },
        )

    assert response.status_code == 201
    assert response.json()["summary"] == "Young relatable comedy viewers"


async def test_audience_intelligence_cross_workspace_access_returns_404(
    override_get_db,
    db_session,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "cross-ws-1")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace1_id))
        workspace2_id = await _create_workspace(client, "cross-ws-2")
        profile_id = await _create_profile(client, workspace1_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace1_id},
            json={"summary": "Secret audience"},
        )

        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace2_id))
        response = await client.get(
            f"/api/v1/profiles/{profile_id}/audience-intelligence",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404
