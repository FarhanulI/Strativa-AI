import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import authenticate_as_workspace_owner


async def create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post("/api/v1/workspaces", json={"name": slug, "slug": slug})
    assert response.status_code == 201
    return response.json()["id"]


async def create_profile(client: AsyncClient, workspace_id: str, name: str) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": "creator", "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def create_opportunity(client: AsyncClient, workspace_id: str, profile_id: str) -> str:
    market = await client.post(
        f"/api/v1/profiles/{profile_id}/market-intelligence",
        params={"workspace_id": workspace_id},
        json={"summary": "Signals"},
    )
    assert market.status_code == 201
    signal = await client.post(
        f"/api/v1/market-intelligence/{market.json()['id']}/signals",
        params={"workspace_id": workspace_id},
        json={"title": "A useful signal", "velocity_score": 1, "engagement_score": 1},
    )
    assert signal.status_code == 201
    opportunity = await client.post(
        f"/api/v1/profiles/{profile_id}/opportunities",
        params={"workspace_id": workspace_id},
        json={
            "source_signal": "trend",
            "market_signal_id": signal.json()["id"],
            "title": "Opportunity title",
            "target_objective": "growth",
            "recommended_format": "reel",
        },
    )
    assert opportunity.status_code == 201
    return opportunity.json()["id"]


async def test_deterministic_brief_crud_and_lifecycle(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "brief-crud")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        opportunity_id = await create_opportunity(client, workspace_id, profile_id)
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
            json={"opportunity_id": opportunity_id},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["generation_source"] == "deterministic"
        assert data["target_objective"] == "growth"
        assert data["recommended_format"] == "reel"
        assert len(data["key_points"]) == 3
        assert data["brief_version"] == "v1"
        brief_id = data["id"]
        ready = await client.patch(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}",
            params={"workspace_id": workspace_id},
            json={"status": "ready", "angle": "A strategic angle"},
        )
        assert ready.status_code == 200
        invalid = await client.patch(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}",
            params={"workspace_id": workspace_id},
            json={"status": "archived"},
        )
        assert invalid.status_code == 404
        listed = await client.get(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1


async def test_manual_brief_requires_strategic_fields_and_is_server_controlled(
    override_get_db,
    db_session,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "brief-manual")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        opportunity_id = await create_opportunity(client, workspace_id, profile_id)
        missing = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
            json={"opportunity_id": opportunity_id, "composition_mode": "manual"},
        )
        assert missing.status_code == 404
        created = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
            json={
                "opportunity_id": opportunity_id,
                "composition_mode": "manual",
                "title": "Manual brief",
                "core_message": "A strategic message.",
            },
        )
        assert created.status_code == 201
        assert created.json()["generation_source"] == "manual"
        assert created.json()["strategic_rationale"]


async def test_brief_workspace_and_profile_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "brief-a")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_a))
        profile_a = await create_profile(client, workspace_a, "A")
        opportunity_id = await create_opportunity(client, workspace_a, profile_a)
        created = await client.post(
            f"/api/v1/profiles/{profile_a}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_a},
            json={"opportunity_id": opportunity_id},
        )
        brief_id = created.json()["id"]

        workspace_b = await create_workspace(client, "brief-b")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_b))
        profile_b = await create_profile(client, workspace_b, "B")

        hidden = await client.get(
            f"/api/v1/profiles/{profile_a}/briefs/{brief_id}",
            params={"workspace_id": workspace_b},
        )
        assert hidden.status_code == 404
        cross_profile = await client.get(
            f"/api/v1/profiles/{profile_b}/briefs/{brief_id}",
            params={"workspace_id": workspace_b},
        )
        assert cross_profile.status_code == 404
