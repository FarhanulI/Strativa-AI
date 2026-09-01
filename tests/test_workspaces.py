import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_create_workspace(override_get_db) -> None:
    """Test creating a workspace"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/workspaces",
            json={"name": "Test Workspace", "slug": "test-workspace-1"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert data["slug"] == "test-workspace-1"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


async def test_get_workspace(override_get_db) -> None:
    """Test getting a workspace by ID"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a workspace
        create_response = await client.post(
            "/api/v1/workspaces",
            json={"name": "Test Workspace", "slug": "test-workspace-2"},
        )
        workspace_id = create_response.json()["id"]

        # Get the workspace
        get_response = await client.get(f"/api/v1/workspaces/{workspace_id}")

    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == workspace_id
    assert data["name"] == "Test Workspace"
    assert data["slug"] == "test-workspace-2"


async def test_list_workspaces(override_get_db) -> None:
    """Test listing workspaces"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create multiple workspaces
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace 1", "slug": "workspace-1"},
        )
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace 2", "slug": "workspace-2"},
        )

        # List workspaces
        list_response = await client.get("/api/v1/workspaces")

    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) >= 2
    slugs = [ws["slug"] for ws in data]
    assert "workspace-1" in slugs
    assert "workspace-2" in slugs


async def test_get_nonexistent_workspace(override_get_db) -> None:
    """Test getting a nonexistent workspace returns 404"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/workspaces/{fake_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


async def test_duplicate_workspace_slug(override_get_db) -> None:
    """Test that duplicate workspace slug is rejected"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create first workspace
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace A", "slug": "duplicate-slug"},
        )

        # Try to create second workspace with same slug
        response = await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace B", "slug": "duplicate-slug"},
        )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


async def test_update_workspace(override_get_db) -> None:
    """Test updating a workspace"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a workspace
        create_response = await client.post(
            "/api/v1/workspaces",
            json={"name": "Original Name", "slug": "original-slug"},
        )
        workspace_id = create_response.json()["id"]

        # Update the workspace
        update_response = await client.patch(
            f"/api/v1/workspaces/{workspace_id}",
            json={"name": "Updated Name"},
        )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Updated Name"
    assert data["slug"] == "original-slug"


async def test_delete_workspace(override_get_db) -> None:
    """Test deleting a workspace"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a workspace
        create_response = await client.post(
            "/api/v1/workspaces",
            json={"name": "To Delete", "slug": "to-delete-workspace"},
        )
        workspace_id = create_response.json()["id"]

        # Delete the workspace
        delete_response = await client.delete(f"/api/v1/workspaces/{workspace_id}")

        # Verify it's deleted
        get_response = await client.get(f"/api/v1/workspaces/{workspace_id}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
