import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests.conftest import authenticate_as_workspace_owner


async def setup(
    client: AsyncClient, db_session: AsyncSession, slug: str = "performance"
) -> tuple[str, str]:
    workspace = await client.post("/api/v1/workspaces", json={"name": slug, "slug": slug})
    await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace.json()["id"]))
    profile = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace.json()["id"]},
        json={"type": "creator", "name": "Football creator", "topics": ["football"]},
    )
    return workspace.json()["id"], profile.json()["id"]


async def add_record(client: AsyncClient, workspace_id: str, profile_id: str, likes: int) -> dict:
    response = await client.post(
        f"/api/v1/profiles/{profile_id}/performance",
        params={"workspace_id": workspace_id},
        json={
            "platform": "instagram",
            "format": "short_video",
            "topic": "football",
            "reach": 100,
            "likes": likes,
            "shares": 10,
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_performance_crud_and_median_analysis(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id, profile_id = await setup(client, db_session)
        for likes in (10, 20, 30):
            await add_record(client, workspace_id, profile_id, likes)
        current = await add_record(client, workspace_id, profile_id, 60)
        analysis = await client.post(
            f"/api/v1/profiles/{profile_id}/performance/{current['id']}/analyze",
            params={"workspace_id": workspace_id},
        )
        assert analysis.status_code == 200, analysis.text
        data = analysis.json()
        assert data["baseline_available"] is True
        assert data["comparables_count"] == 3
        assert data["performance_classification"] == "strong"
        assert data["evidence"]["metrics"]["engagement_rate"]["relative"] == 2.3333333333333335


async def test_performance_validation_and_workspace_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id, profile_id = await setup(client, db_session, "performance-isolated")
        invalid = await client.post(
            f"/api/v1/profiles/{profile_id}/performance",
            params={"workspace_id": workspace_id},
            json={"platform": "instagram", "reach": -1},
        )
        assert invalid.status_code == 422
        record = await add_record(client, workspace_id, profile_id, 10)
        other = await client.post("/api/v1/workspaces", json={"name": "other", "slug": "other"})
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(other.json()["id"]))
        hidden = await client.get(
            f"/api/v1/profiles/{profile_id}/performance/{record['id']}",
            params={"workspace_id": other.json()["id"]},
        )
        assert hidden.status_code == 404
