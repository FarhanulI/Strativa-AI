import uuid
from datetime import datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_content_briefs import create_opportunity, create_profile, create_workspace
from tests.test_content_drafts import create_ready_brief


async def create_ready_draft(
    client: AsyncClient,
    workspace_id: str,
    profile_id: str,
    brief_id: str,
    title: str,
    hook: str,
    body: str,
    cta: str = "Read more",
) -> dict:
    created = await client.post(
        f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
        params={"workspace_id": workspace_id},
        json={
            "composition_mode": "manual",
            "title": title,
            "hook": hook,
            "body": body,
            "cta": cta,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


async def add_selected_caption(
    client: AsyncClient, workspace_id: str, profile_id: str, draft_id: str
) -> str:
    generated = await client.post(
        f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations",
        params={"workspace_id": workspace_id},
        json={"variation_type": "caption", "count": 1, "use_ai": False},
    )
    assert generated.status_code == 201, generated.text
    variation = generated.json()[0]

    selected = await client.patch(
        f"/api/v1/profiles/{profile_id}/drafts/{draft_id}/variations/{variation['id']}",
        params={"workspace_id": workspace_id},
        json={"is_selected": True},
    )
    assert selected.status_code == 200, selected.text
    return selected.json()["content"]


async def test_library_list_filters_pagination_and_sorting(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-list")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        first = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Alpha title",
            hook="Alpha hook",
            body="Alpha body",
        )
        second = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Bravo title",
            hook="Bravo hook",
            body="Bravo body",
        )

        ready = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{second['id']}",
            params={"workspace_id": workspace_id},
            json={"status": "ready"},
        )
        assert ready.status_code == 200

        all_items = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "sort_by": "created_at", "sort": "desc"},
        )
        assert all_items.status_code == 200
        data = all_items.json()
        assert len(data) == 2
        assert data[0]["id"] == second["id"]
        assert {item["id"] for item in data} == {first["id"], second["id"]}

        filtered = await client.get(
            "/api/v1/library",
            params={
                "workspace_id": workspace_id,
                "profile_id": profile_id,
                "status": "ready",
                "platform": second["platform"],
                "format": second["format"],
            },
        )
        assert filtered.status_code == 200
        filtered_data = filtered.json()
        assert len(filtered_data) == 1
        assert filtered_data[0]["id"] == second["id"]

        paged = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "skip": 0, "limit": 1},
        )
        assert paged.status_code == 200
        assert len(paged.json()) == 1

        empty_page = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "skip": 2, "limit": 100},
        )
        assert empty_page.status_code == 200
        assert empty_page.json() == []


async def test_library_list_date_range_filters(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-date")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        first = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Date one",
            hook="Date hook one",
            body="Date body one",
        )
        second = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Date two",
            hook="Date hook two",
            body="Date body two",
        )

        created_after = first["created_at"]
        newer = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "created_after": created_after},
        )
        assert newer.status_code == 200
        assert {item["id"] for item in newer.json()} >= {first["id"], second["id"]}

        before_dt = datetime.fromisoformat(second["created_at"].replace("Z", "+00:00")) - timedelta(
            microseconds=1
        )
        older = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "created_before": before_dt.isoformat()},
        )
        assert older.status_code == 200
        older_ids = {item["id"] for item in older.json()}
        assert first["id"] in older_ids
        assert second["id"] not in older_ids


async def test_library_search_matches_title_hook_and_caption(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-search")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        draft_a = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Football Breakdown",
            hook="Tactical pressing masterclass",
            body="Body A",
        )
        draft_b = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Creator Systems",
            hook="Hook B",
            body="Body B",
        )
        caption = await add_selected_caption(client, workspace_id, profile_id, draft_b["id"])

        title_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": "football"},
        )
        assert title_match.status_code == 200
        assert {item["id"] for item in title_match.json()} == {draft_a["id"]}

        hook_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": "pressing"},
        )
        assert hook_match.status_code == 200
        assert {item["id"] for item in hook_match.json()} == {draft_a["id"]}

        caption_probe = next((word for word in caption.split(" ") if len(word) > 4), caption)
        caption_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": caption_probe.lower()},
        )
        assert caption_match.status_code == 200
        assert draft_b["id"] in {item["id"] for item in caption_match.json()}

        no_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": "does-not-exist"},
        )
        assert no_match.status_code == 200
        assert no_match.json() == []


async def test_library_retrieve_attaches_lineage_summary(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-lineage")
        profile_id = await create_profile(client, workspace_id, "Creator")
        opportunity_id = await create_opportunity(client, workspace_id, profile_id)

        brief_response = await client.post(
            f"/api/v1/profiles/{profile_id}/opportunities/{opportunity_id}/briefs",
            params={"workspace_id": workspace_id},
            json={"opportunity_id": opportunity_id},
        )
        assert brief_response.status_code == 201
        brief_id = brief_response.json()["id"]

        ready = await client.patch(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}",
            params={"workspace_id": workspace_id},
            json={"status": "ready", "angle": "Lineage angle"},
        )
        assert ready.status_code == 200

        draft = await client.post(
            f"/api/v1/profiles/{profile_id}/briefs/{brief_id}/drafts",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert draft.status_code == 201
        draft_id = draft.json()["id"]

        response = await client.get(
            f"/api/v1/library/{draft_id}",
            params={"workspace_id": workspace_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["draft"]["id"] == draft_id
        assert data["brief"]["id"] == brief_id
        assert data["opportunity"]["id"] == opportunity_id
        assert data["brief"]["title"]
        assert data["opportunity"]["title"]


async def test_library_cross_workspace_and_profile_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "library-a")
        workspace_b = await create_workspace(client, "library-b")
        profile_a = await create_profile(client, workspace_a, "A")
        profile_b = await create_profile(client, workspace_b, "B")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        brief_b = await create_ready_brief(client, workspace_b, profile_b)

        draft_a = await create_ready_draft(
            client,
            workspace_a,
            profile_a,
            brief_a,
            title="Workspace A",
            hook="Hook A",
            body="Body A",
        )
        await create_ready_draft(
            client,
            workspace_b,
            profile_b,
            brief_b,
            title="Workspace B",
            hook="Hook B",
            body="Body B",
        )

        list_a = await client.get("/api/v1/library", params={"workspace_id": workspace_a})
        assert list_a.status_code == 200
        assert {item["id"] for item in list_a.json()} == {draft_a["id"]}

        cross_profile_filter = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_a, "profile_id": profile_b},
        )
        assert cross_profile_filter.status_code == 404

        hidden = await client.get(
            f"/api/v1/library/{draft_a['id']}",
            params={"workspace_id": workspace_b},
        )
        assert hidden.status_code == 404


async def test_library_empty_and_unknown_draft(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-empty")

        empty = await client.get("/api/v1/library", params={"workspace_id": workspace_id})
        assert empty.status_code == 200
        assert empty.json() == []

        unknown = await client.get(
            f"/api/v1/library/{uuid.uuid4()}",
            params={"workspace_id": workspace_id},
        )
        assert unknown.status_code == 404
