from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Workspace {slug}", "slug": slug},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_profile(client: AsyncClient, workspace_id: str, type_: str, name: str) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": type_, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_brand_for_creator(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-create-creator")
        profile_id = await _create_profile(client, workspace_id, "creator", "Rahim Sports")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={
                "positioning": "An energetic football commentator",
                "personality": ["Energetic", "Opinionated", "Friendly"],
                "voice": {"style": "conversational", "energy": "high"},
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["content_profile_id"] == profile_id
    assert data["positioning"] == "An energetic football commentator"


async def test_create_brand_for_business(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-create-business")
        profile_id = await _create_profile(client, workspace_id, "business", "ABC Sports")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={
                "positioning": "Affordable premium sportswear for young athletes.",
                "personality": ["Energetic", "Community-focused", "Approachable"],
            },
        )

    assert response.status_code == 201
    assert response.json()["content_profile_id"] == profile_id


async def test_get_brand(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-get")
        profile_id = await _create_profile(client, workspace_id, "creator", "Creator One")

        create_response = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "Market leader"},
        )
        brand_id = create_response.json()["id"]

        get_response = await client.get(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
        )

    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == brand_id
    assert data["content_profile_id"] == profile_id


async def test_update_brand(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-update")
        profile_id = await _create_profile(client, workspace_id, "creator", "Creator One")

        await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "Original"},
        )

        response = await client.patch(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "Updated", "mission": "Make football simpler"},
        )

    assert response.status_code == 200
    assert response.json()["positioning"] == "Updated"
    assert response.json()["mission"] == "Make football simpler"


async def test_delete_brand(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-delete")
        profile_id = await _create_profile(client, workspace_id, "creator", "Creator One")

        await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "To Delete"},
        )

        delete_response = await client.delete(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
        )
        get_response = await client.get(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


async def test_duplicate_brand_returns_409(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-duplicate")
        profile_id = await _create_profile(client, workspace_id, "business", "Business One")

        first = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "First"},
        )
        second = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "Second"},
        )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Brand profile already exists for this content profile."


async def test_cross_workspace_brand_access_returns_404(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await _create_workspace(client, "brand-cross-a")
        workspace_b = await _create_workspace(client, "brand-cross-b")
        profile_id = await _create_profile(client, workspace_a, "creator", "Creator A")

        await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_a},
            json={"positioning": "Workspace A brand"},
        )

        response = await client.get(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_b},
        )

    assert response.status_code == 404


async def test_inaccessible_profile_cannot_create_brand(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await _create_workspace(client, "brand-create-cross-a")
        workspace_b = await _create_workspace(client, "brand-create-cross-b")
        profile_id = await _create_profile(client, workspace_a, "business", "Business A")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_b},
            json={"positioning": "Should fail"},
        )

    assert response.status_code == 404


async def test_deleting_content_profile_cascades_to_brand(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "brand-cascade")
        profile_id = await _create_profile(client, workspace_id, "creator", "Cascade Profile")

        create_brand = await client.post(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
            json={"positioning": "Cascade Test"},
        )
        assert create_brand.status_code == 201

        delete_profile = await client.delete(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )
        assert delete_profile.status_code == 204

        get_brand = await client.get(
            f"/api/v1/profiles/{profile_id}/brand",
            params={"workspace_id": workspace_id},
        )

    assert get_brand.status_code == 404
