import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ai.router import AIResult
from app.services.ai.schemas.responses import AIResponseMetadata
from tests.test_content_briefs import create_opportunity, create_profile, create_workspace
from tests.test_content_drafts import create_ready_brief


async def create_draft_from_brief(
    client: AsyncClient, workspace_id: str, profile_id: str, brief_id: str
) -> str:
    created = await client.post(
        f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
        params={"workspace_id": workspace_id},
        json={},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def create_draft(client: AsyncClient, workspace_id: str, profile_id: str) -> str:
    brief_id = await create_ready_brief(client, workspace_id, profile_id)
    return await create_draft_from_brief(client, workspace_id, profile_id, brief_id)


async def test_deterministic_hook_variations(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-hook")
        profile_id = await create_profile(client, workspace_id, "Creator")
        draft_id = await create_draft(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 3, "use_ai": False},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert len(data) == 3
        assert [v["variation_index"] for v in data] == [1, 2, 3]
        for v in data:
            assert v["generation_source"] == "deterministic"
            assert v["ai_provider"] is None
            assert v["content"]
            assert v["rationale"]


async def test_deterministic_caption_variations_count_bounds(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-caption")
        profile_id = await create_profile(client, workspace_id, "Creator")
        draft_id = await create_draft(client, workspace_id, profile_id)

        too_many = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "caption", "count": 6, "use_ai": False},
        )
        assert too_many.status_code == 422

        too_few = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "caption", "count": 0, "use_ai": False},
        )
        assert too_few.status_code == 422

        exactly_five = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "caption", "count": 5, "use_ai": False},
        )
        assert exactly_five.status_code == 201
        assert len(exactly_five.json()) == 5

        one = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "caption", "count": 1, "use_ai": False},
        )
        assert one.status_code == 201
        assert len(one.json()) == 1
        # indexes continue from the previous batch
        assert one.json()[0]["variation_index"] == 6


async def test_ai_variation_generation_and_fallback(monkeypatch, override_get_db) -> None:
    async def fake_generate(self, variation_type, count, brief, draft):
        from app.schemas.content_draft_variation import (
            ContentVariationLLMItem,
            ContentVariationLLMResult,
        )

        items = [
            ContentVariationLLMItem(
                content=f"AI {variation_type.value} {i}", rationale="Because AI"
            )
            for i in range(count)
        ]
        return ContentVariationLLMResult(variations=items), AIResult(
            output=ContentVariationLLMResult(variations=items),
            metadata=AIResponseMetadata(provider="gemini", model="test-model"),
        )

    monkeypatch.setattr(
        "app.services.content_creation.variation_generator.ContentDraftVariationGenerator.generate",
        fake_generate,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-ai")
        profile_id = await create_profile(client, workspace_id, "Creator")
        draft_id = await create_draft(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 3, "use_ai": True},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert len(data) == 3
        for v in data:
            assert v["generation_source"] == "ai"
            assert v["ai_provider"] == "gemini"
            assert v["prompt_version"]

    async def failing_generate(self, variation_type, count, brief, draft):
        raise RuntimeError("provider failure")

    monkeypatch.setattr(
        "app.services.content_creation.variation_generator.ContentDraftVariationGenerator.generate",
        failing_generate,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fallback = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "caption", "count": 2, "use_ai": True},
        )
        assert fallback.status_code == 201, fallback.text
        data = fallback.json()
        assert len(data) == 2
        for v in data:
            assert v["generation_source"] == "deterministic"
            assert v["ai_provider"] is None
        assert "provider failure" not in fallback.text


async def test_malformed_ai_response_falls_back_partially(monkeypatch, override_get_db) -> None:
    async def partial_generate(self, variation_type, count, brief, draft):
        from app.schemas.content_draft_variation import (
            ContentVariationLLMItem,
            ContentVariationLLMResult,
        )

        items = [ContentVariationLLMItem(content="Only one", rationale="Because AI")]
        return ContentVariationLLMResult(variations=items), AIResult(
            output=ContentVariationLLMResult(variations=items),
            metadata=AIResponseMetadata(provider="gemini", model="test-model"),
        )

    monkeypatch.setattr(
        "app.services.content_creation.variation_generator.ContentDraftVariationGenerator.generate",
        partial_generate,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-partial")
        profile_id = await create_profile(client, workspace_id, "Creator")
        draft_id = await create_draft(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 3, "use_ai": True},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert len(data) == 3
        sources = sorted(v["generation_source"] for v in data)
        assert sources == ["ai", "deterministic", "deterministic"]


async def test_selection_updates_draft_and_replaces_previous_selection(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-select")
        profile_id = await create_profile(client, workspace_id, "Creator")
        draft_id = await create_draft(client, workspace_id, profile_id)

        hooks = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 2, "use_ai": False},
        )
        hook_ids = [v["id"] for v in hooks.json()]

        captions = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "caption", "count": 2, "use_ai": False},
        )
        caption_ids = [v["id"] for v in captions.json()]

        select_hook = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations/{hook_ids[0]}",
            params={"workspace_id": workspace_id},
            json={"is_selected": True},
        )
        assert select_hook.status_code == 200
        assert select_hook.json()["is_selected"] is True

        select_caption = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations/{caption_ids[0]}",
            params={"workspace_id": workspace_id},
            json={"is_selected": True},
        )
        assert select_caption.status_code == 200

        draft = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}",
            params={"workspace_id": workspace_id},
        )
        assert draft.json()["hook"] == select_hook.json()["content"]
        assert draft.json()["caption"] == select_caption.json()["content"]
        # unrelated fields untouched
        assert draft.json()["brief_id"]
        assert draft.json()["body"]

        # replace the selected hook
        select_other_hook = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations/{hook_ids[1]}",
            params={"workspace_id": workspace_id},
            json={"is_selected": True},
        )
        assert select_other_hook.status_code == 200

        listed = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id, "variation_type": "hook"},
        )
        selected = [v for v in listed.json() if v["is_selected"]]
        assert len(selected) == 1
        assert selected[0]["id"] == hook_ids[1]

        draft_after = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}",
            params={"workspace_id": workspace_id},
        )
        assert draft_after.json()["hook"] == select_other_hook.json()["content"]
        assert draft_after.json()["caption"] == select_caption.json()["content"]


async def test_cannot_select_variation_from_another_draft(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-cross-draft")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft_a = await create_draft_from_brief(client, workspace_id, profile_id, brief_id)
        draft_b = await create_draft_from_brief(client, workspace_id, profile_id, brief_id)

        variations = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_a}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 1, "use_ai": False},
        )
        variation_id = variations.json()[0]["id"]

        response = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_b}/variations/{variation_id}",
            params={"workspace_id": workspace_id},
            json={"is_selected": True},
        )
        assert response.status_code == 404


async def test_variation_profile_and_workspace_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "var-a")
        workspace_b = await create_workspace(client, "var-b")
        profile_a = await create_profile(client, workspace_a, "A")
        profile_b = await create_profile(client, workspace_b, "B")
        draft_id = await create_draft(client, workspace_a, profile_a)

        cross_workspace = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_b},
            json={"variation_type": "hook", "count": 1, "use_ai": False},
        )
        assert cross_workspace.status_code == 404

        cross_profile = await client.get(
            f"/api/v1/profiles/{profile_b}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_b},
        )
        assert cross_profile.status_code == 404


async def test_business_profile_without_and_with_business_context(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-business")
        profile_response = await client.post(
            "/api/v1/profiles",
            params={"workspace_id": workspace_id},
            json={"type": "business", "name": "Acme"},
        )
        assert profile_response.status_code == 201
        profile_id = profile_response.json()["id"]

        business_context = await client.post(
            f"/api/v1/profiles/{profile_id}/business-context",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert business_context.status_code == 201, business_context.text

        opportunity_id = await create_opportunity(client, workspace_id, profile_id)
        brief = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
            json={"opportunity_id": opportunity_id},
        )
        assert brief.status_code == 201
        brief_id = brief.json()["id"]
        await client.patch(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}",
            params={"workspace_id": workspace_id},
            json={"status": "ready", "angle": "Explain the strategic angle."},
        )
        draft = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert draft.status_code == 201, draft.text
        draft_id = draft.json()["id"]

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 2, "use_ai": False},
        )
        assert response.status_code == 201, response.text
        assert len(response.json()) == 2


async def test_generate_variations_for_unknown_draft_returns_404(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-unknown-draft")
        profile_id = await create_profile(client, workspace_id, "Creator")
        unknown_draft_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{unknown_draft_id}/variations",
            params={"workspace_id": workspace_id},
            json={"variation_type": "hook", "count": 1, "use_ai": False},
        )
        assert response.status_code == 404


async def test_select_unknown_variation_returns_404(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "var-unknown-variation")
        profile_id = await create_profile(client, workspace_id, "Creator")
        draft_id = await create_draft(client, workspace_id, profile_id)
        unknown_variation_id = str(uuid.uuid4())

        response = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations/{unknown_variation_id}",
            params={"workspace_id": workspace_id},
            json={"is_selected": True},
        )
        assert response.status_code == 404
