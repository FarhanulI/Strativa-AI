import uuid

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


async def test_create_pain_point(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-create")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={
                "title": "Expensive sportswear",
                "description": "Customers find sportswear too expensive",
                "severity": 4,
                "frequency": 5,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Expensive sportswear"
    assert data["severity"] == 4
    assert data["frequency"] == 5


async def test_list_pain_points(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-list")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "Pain 1", "severity": 3},
        )
        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "Pain 2", "severity": 4},
        )

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_get_pain_point(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-get")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "Test Pain"},
        )
        pain_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points/{pain_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Test Pain"


async def test_update_pain_point(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-update")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "Original", "severity": 2},
        )
        pain_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points/{pain_id}",
            params={"workspace_id": workspace_id},
            json={"severity": 5},
        )

    assert response.status_code == 200
    assert response.json()["severity"] == 5


async def test_delete_pain_point(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-delete")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "To Delete"},
        )
        pain_id = create_response.json()["id"]

        response = await client.delete(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points/{pain_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_severity_validation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-severity")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "Test", "severity": 10},
        )

    assert response.status_code == 422


async def test_frequency_validation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "pain-frequency")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace_id},
            json={"title": "Test", "frequency": 0},
        )

    assert response.status_code == 422


async def test_pain_point_workspace_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "pain-iso-1")
        workspace2_id = await _create_workspace(client, "pain-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace1_id, profile_id)

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/pain-points",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404
