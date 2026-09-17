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


async def test_create_creator_profile(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-create-creator")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={
                "type": "creator",
                "name": "Rahim Sports",
                "description": "Football content creator",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "creator"
    assert data["name"] == "Rahim Sports"
    assert data["workspace_id"] == workspace_id


async def test_create_business_profile(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-create-business")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "business", "name": "ABC Sports"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "business"
    assert data["name"] == "ABC Sports"


async def test_get_profile(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-get")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Creator One"},
        )
        profile_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["id"] == profile_id


async def test_list_profiles(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Creator One"},
        )
        await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "business", "name": "Business One"},
        )

        response = await client.get(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_update_profile(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-update")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Original"},
        )
        profile_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
            json={"name": "Updated", "positioning": "Simple football analysis"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["positioning"] == "Simple football analysis"


async def test_delete_profile(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-delete")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "To Delete"},
        )
        profile_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )
        get_response = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


async def test_invalid_profile_type(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-invalid-type")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "agency", "name": "Not yet supported"},
        )

    assert response.status_code == 422


async def test_workspace_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await _create_workspace(client, "profiles-isolation-a")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_a))
        workspace_b = await _create_workspace(client, "profiles-isolation-b")

        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_a},
            json={"type": "creator", "name": "A profile"},
        )
        profile_id = create_response.json()["id"]

        get_own = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_a},
        )
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_b))
        get_cross = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_b},
        )

    assert get_own.status_code == 200
    assert get_cross.status_code == 404


async def test_topics_persistence(override_get_db, db_session) -> None:
    topics = ["football", "sports"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-topics")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Topics Test", "topics": topics},
        )
        profile_id = create_response.json()["id"]

        get_response = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )

    assert get_response.status_code == 200
    assert get_response.json()["topics"] == topics


async def test_expertise_persistence(override_get_db, db_session) -> None:
    expertise = ["football analysis"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-expertise")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Expertise Test", "expertise": expertise},
        )
        profile_id = create_response.json()["id"]

        get_response = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )

    assert get_response.status_code == 200
    assert get_response.json()["expertise"] == expertise


async def test_goals_persistence(override_get_db, db_session) -> None:
    goals = ["audience_growth", "authority"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-goals")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        create_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "creator", "name": "Goals Test", "goals": goals},
        )
        profile_id = create_response.json()["id"]

        get_response = await client.get(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )

    assert get_response.status_code == 200
    assert get_response.json()["goals"] == goals


async def test_get_nonexistent_profile(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "profiles-missing")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        response = await client.get(
            f"/api/v1/profiles/{uuid.uuid4()}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Content profile not found"
