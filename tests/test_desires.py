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


async def _create_audience_intelligence(
    client: AsyncClient, workspace_id: str, profile_id: str
) -> str:
    response = await client.post(
        f"/api/v1/profiles/{profile_id}/audience-intelligence",
        params={"workspace_id": workspace_id},
        json={"summary": "Test audience"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_desire(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "desire-create")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={
                "title": "Affordable quality",
                "description": "Want quality at affordable prices",
                "importance": 5,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Affordable quality"
    assert data["importance"] == 5


async def test_list_desires(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "desire-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={"title": "Desire 1", "importance": 3},
        )
        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={"title": "Desire 2", "importance": 4},
        )

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_get_desire(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "desire-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={"title": "Test Desire"},
        )
        desire_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/desires/{desire_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Test Desire"


async def test_update_desire(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "desire-update")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={"title": "Original", "importance": 2},
        )
        desire_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/audience-intelligence/{audience_id}/desires/{desire_id}",
            params={"workspace_id": workspace_id},
            json={"importance": 5},
        )

    assert response.status_code == 200
    assert response.json()["importance"] == 5


async def test_delete_desire(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "desire-delete")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={"title": "To Delete"},
        )
        desire_id = create_response.json()["id"]

        response = await client.delete(
            f"/api/v1/audience-intelligence/{audience_id}/desires/{desire_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_importance_validation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "desire-importance")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace_id},
            json={"title": "Test", "importance": 10},
        )

    assert response.status_code == 422


async def test_desire_workspace_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "desire-iso-1")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace1_id))
        workspace2_id = await _create_workspace(client, "desire-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace1_id, profile_id)

        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace2_id))
        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/desires",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404
