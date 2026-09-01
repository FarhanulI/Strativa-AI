from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Workspace {slug}", "slug": slug},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_profile(
    client: AsyncClient,
    workspace_id: str,
    name: str,
    profile_type: str = "creator",
) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": profile_type, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-create")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={
                "summary": "Football content trends",
                "market_context": "Bangladesh short-form video market",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["summary"] == "Football content trends"
    assert data["market_context"] == "Bangladesh short-form video market"
    assert data["content_profile_id"] == profile_id


async def test_get_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-get")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Summary"},
        )

        response = await client.get(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["summary"] == "Summary"


async def test_update_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-update")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Original"},
        )

        response = await client.patch(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Updated"},
        )

    assert response.status_code == 200
    assert response.json()["summary"] == "Updated"


async def test_delete_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-delete")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "To delete"},
        )

        response = await client.delete(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
        )
    assert response.status_code == 204


async def test_duplicate_market_intelligence_returns_409(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-dup")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "First"},
        )
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Second"},
        )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


async def test_creator_can_create_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-creator")
        profile_id = await _create_profile(
            client, workspace_id, "Football Creator", profile_type="creator"
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Football conversations"},
        )

    assert response.status_code == 201


async def test_creator_market_intelligence_without_business_context(override_get_db) -> None:
    """A creator profile must be able to have MarketIntelligence with no BusinessContext."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-no-business")
        profile_id = await _create_profile(
            client, workspace_id, "Football Creator", profile_type="creator"
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Football conversations"},
        )
        assert response.status_code == 201

        business_response = await client.get(
            f"/api/v1/profiles/{profile_id}/business-context",
            params={"workspace_id": workspace_id},
        )

    assert business_response.status_code == 404


async def test_business_can_create_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-business")
        profile_id = await _create_profile(
            client, workspace_id, "Sportswear Co", profile_type="business"
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={
                "summary": "Football apparel market",
                "market_context": "Rising demand for lightweight jerseys",
            },
        )

    assert response.status_code == 201


async def test_market_intelligence_cross_workspace_returns_404(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "market-xw-1")
        workspace2_id = await _create_workspace(client, "market-xw-2")
        profile_id = await _create_profile(client, workspace1_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace1_id},
            json={"summary": "Secret"},
        )

        response = await client.get(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404


async def test_deleting_content_profile_cascades_market_intelligence(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "market-cascade")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")

        await client.post(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
            json={"summary": "Cascade target"},
        )

        delete_profile_response = await client.delete(
            f"/api/v1/profiles/{profile_id}",
            params={"workspace_id": workspace_id},
        )
        assert delete_profile_response.status_code == 204

        response = await client.get(
            f"/api/v1/profiles/{profile_id}/market-intelligence",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 404
