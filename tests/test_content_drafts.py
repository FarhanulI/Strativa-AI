from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ai.router import AIResult
from app.services.ai.schemas.responses import AIResponseMetadata
from tests.test_content_briefs import create_opportunity, create_profile, create_workspace


async def create_ready_brief(client: AsyncClient, workspace_id: str, profile_id: str) -> str:
    opportunity_id = await create_opportunity(client, workspace_id, profile_id)
    created = await client.post(
        f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
        params={"workspace_id": workspace_id},
        json={"opportunity_id": opportunity_id},
    )
    assert created.status_code == 201
    brief_id = created.json()["id"]
    ready = await client.patch(
        f"/api/v1/profiles/{profile_id}/briefs/{brief_id}",
        params={"workspace_id": workspace_id},
        json={"status": "ready", "angle": "Explain the strategic angle."},
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready", ready.text
    return brief_id


async def test_deterministic_draft_crud_and_lifecycle(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "draft-crud")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        created = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert created.status_code == 201, created.text
        data = created.json()
        assert data["generation_source"] == "deterministic"
        assert data["composition_mode"] == "compose"
        assert data["brief_id"] == brief_id
        assert data["draft_metadata"]["lineage"]["brief_id"] == brief_id
        draft_id = data["id"]

        ready = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}",
            params={"workspace_id": workspace_id},
            json={"status": "ready", "body": "Updated body"},
        )
        assert ready.status_code == 200
        listed = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts",
            params={"workspace_id": workspace_id, "status": "ready"},
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        deleted = await client.delete(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}",
            params={"workspace_id": workspace_id},
        )
        assert deleted.status_code == 204


async def test_manual_draft_preserves_content_and_rejects_non_executable_brief(
    override_get_db,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "draft-manual")
        profile_id = await create_profile(client, workspace_id, "Creator")
        opportunity_id = await create_opportunity(client, workspace_id, profile_id)
        brief = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
            json={"opportunity_id": opportunity_id},
        )
        rejected = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief.json()['id']}/drafts",
            params={"workspace_id": workspace_id},
            json={"composition_mode": "manual", "hook": "Hook", "body": "Body"},
        )
        assert rejected.status_code == 404

        ready = await client.patch(
            f"/api/v1/profiles/{profile_id}/briefs/{brief.json()['id']}",
            params={"workspace_id": workspace_id},
            json={"status": "ready"},
        )
        assert ready.status_code == 200
        brief_id = brief.json()["id"]
        created = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_id},
            json={
                "composition_mode": "manual",
                "title": "Manual title",
                "hook": "Manual hook",
                "body": "Manual body",
                "cta": "Manual CTA",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["generation_source"] == "manual"
        assert created.json()["body"] == "Manual body"


async def test_ai_draft_and_failure_fallback(monkeypatch, override_get_db) -> None:
    async def fake_create(self, brief):
        from app.schemas.content_draft import ContentCreationLLMResult

        return ContentCreationLLMResult(
            title="AI title", hook="AI hook", body="AI body", cta="AI CTA"
        ), AIResult(
            output=ContentCreationLLMResult(
                title="AI title", hook="AI hook", body="AI body", cta="AI CTA"
            ),
            metadata=AIResponseMetadata(provider="gemini", model="test-model"),
        )

    monkeypatch.setattr("app.services.content_creation.creator.ContentCreator.create", fake_create)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "draft-ai")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        created = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_id},
            json={"use_ai": True},
        )
        assert created.status_code == 201, created.text
        assert created.json()["generation_source"] == "ai"
        assert created.json()["ai_provider"] == "gemini"

    async def failing_create(self, brief):
        raise RuntimeError("provider failure")

    monkeypatch.setattr(
        "app.services.content_creation.creator.ContentCreator.create", failing_create
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fallback = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_id},
            json={"use_ai": True},
        )
        assert fallback.status_code == 201
        assert fallback.json()["generation_source"] == "ai_fallback"
        assert fallback.json()["body"]
        assert "provider failure" not in fallback.text


async def test_draft_profile_and_workspace_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "draft-a")
        workspace_b = await create_workspace(client, "draft-b")
        profile_a = await create_profile(client, workspace_a, "A")
        profile_b = await create_profile(client, workspace_b, "B")
        brief_id = await create_ready_brief(client, workspace_a, profile_a)
        created = await client.post(
            f"/api/v1/profiles/{profile_a}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_a},
            json={},
        )
        assert created.status_code == 201, created.text
        draft_id = created.json()["id"]
        cross_workspace = await client.get(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_id}",
            params={"workspace_id": workspace_b},
        )
        cross_profile = await client.get(
            f"/api/v1/profiles/{profile_b}/drafts/{draft_id}",
            params={"workspace_id": workspace_b},
        )
        assert cross_workspace.status_code == 404
        assert cross_profile.status_code == 404
