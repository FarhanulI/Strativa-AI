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


async def test_create_persona(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "persona-create")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
            json={
                "name": "Young Casual Viewer",
                "description": "18-25 year old social media user",
                "demographics": {"age_range": "18-25"},
                "goals": ["entertainment"],
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Young Casual Viewer"
    assert data["goals"] == ["entertainment"]


async def test_list_personas(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "persona-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
            json={"name": "Persona 1"},
        )
        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
            json={"name": "Persona 2"},
        )

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_get_persona(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "persona-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
            json={"name": "Test Persona"},
        )
        persona_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/personas/{persona_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Test Persona"


async def test_update_persona(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "persona-update")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
            json={"name": "Original Name"},
        )
        persona_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/audience-intelligence/{audience_id}/personas/{persona_id}",
            params={"workspace_id": workspace_id},
            json={"name": "Updated Name"},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


async def test_delete_persona(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "persona-delete")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace_id},
            json={"name": "To Delete"},
        )
        persona_id = create_response.json()["id"]

        response = await client.delete(
            f"/api/v1/audience-intelligence/{audience_id}/personas/{persona_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_persona_workspace_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "persona-iso-1")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace1_id))
        workspace2_id = await _create_workspace(client, "persona-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace1_id, profile_id)

        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace2_id))
        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/personas",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404
