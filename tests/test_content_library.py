import uuid
from datetime import datetime, timedelta

import fakeredis.aioredis as fakeredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import authenticate_as_workspace_owner
from tests.test_content_briefs import create_opportunity, create_profile, create_workspace
from tests.test_content_drafts import create_ready_brief


@pytest.fixture(autouse=True)
def _fake_cache_redis(monkeypatch: pytest.MonkeyPatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.api.v1.content_library.get_redis", lambda: fake)
    monkeypatch.setattr("app.services.content_library.get_redis", lambda: fake)
    yield fake


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


async def test_library_list_filters_and_sorting(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-list")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
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
        assert data["has_more"] is False
        assert data["next_cursor"] is None
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == second["id"]
        assert {item["id"] for item in data["items"]} == {first["id"], second["id"]}

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
        filtered_items = filtered.json()["items"]
        assert len(filtered_items) == 1
        assert filtered_items[0]["id"] == second["id"]


async def test_library_cursor_pagination_pages_without_skip_or_duplicate(
    override_get_db,
    db_session,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-cursor")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        drafts = []
        for i in range(5):
            drafts.append(
                await create_ready_draft(
                    client,
                    workspace_id,
                    profile_id,
                    brief_id,
                    title=f"Draft {i}",
                    hook=f"Hook {i}",
                    body=f"Body {i}",
                )
            )
        # Creation order is oldest -> newest: drafts[0] .. drafts[4].

        page1 = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "page_size": 2},
        )
        assert page1.status_code == 200
        page1_data = page1.json()
        assert [item["id"] for item in page1_data["items"]] == [
            drafts[4]["id"],
            drafts[3]["id"],
        ]
        assert page1_data["has_more"] is True
        cursor = page1_data["next_cursor"]
        assert cursor

        # Simulate a concurrent insert landing at the very top (newest)
        # between the two page fetches -- the classic failure mode for
        # offset pagination (it would shift every subsequent page's window
        # by one, duplicating or skipping a row). A cursor keyed off the
        # last-seen (sort_key, id) must be unaffected by it.
        concurrent = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Concurrent insert",
            hook="Concurrent hook",
            body="Concurrent body",
        )

        page2 = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "page_size": 2, "cursor": cursor},
        )
        assert page2.status_code == 200
        page2_data = page2.json()
        assert [item["id"] for item in page2_data["items"]] == [
            drafts[2]["id"],
            drafts[1]["id"],
        ]
        assert concurrent["id"] not in {item["id"] for item in page2_data["items"]}
        assert page2_data["has_more"] is True

        page3 = await client.get(
            "/api/v1/library",
            params={
                "workspace_id": workspace_id,
                "page_size": 2,
                "cursor": page2_data["next_cursor"],
            },
        )
        assert page3.status_code == 200
        page3_data = page3.json()
        assert [item["id"] for item in page3_data["items"]] == [drafts[0]["id"]]
        assert page3_data["has_more"] is False
        assert page3_data["next_cursor"] is None

        # Across all pages fetched, every pre-existing draft appears exactly
        # once -- no skip, no duplicate.
        seen = (
            [item["id"] for item in page1_data["items"]]
            + [item["id"] for item in page2_data["items"]]
            + [item["id"] for item in page3_data["items"]]
        )
        assert sorted(seen) == sorted(d["id"] for d in drafts)
        assert len(seen) == len(set(seen))


async def test_library_invalid_cursor_rejected(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-bad-cursor")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))

        bad = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "cursor": "not-a-valid-cursor"},
        )
        assert bad.status_code == 400


async def test_library_cursor_rejects_mismatched_sort(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-cursor-mismatch")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        await create_ready_draft(
            client, workspace_id, profile_id, brief_id, title="A", hook="A", body="A"
        )
        await create_ready_draft(
            client, workspace_id, profile_id, brief_id, title="B", hook="B", body="B"
        )

        first_page = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "page_size": 1, "sort_by": "created_at"},
        )
        cursor = first_page.json()["next_cursor"]

        mismatched = await client.get(
            "/api/v1/library",
            params={
                "workspace_id": workspace_id,
                "page_size": 1,
                "sort_by": "updated_at",
                "cursor": cursor,
            },
        )
        assert mismatched.status_code == 400


async def test_library_max_page_size_enforced(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-max-page")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        for i in range(60):
            await create_ready_draft(
                client,
                workspace_id,
                profile_id,
                brief_id,
                title=f"Bulk {i}",
                hook=f"Bulk hook {i}",
                body=f"Bulk body {i}",
            )

        response = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "page_size": 1000},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 50
        assert data["has_more"] is True


async def test_library_list_date_range_filters(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-date")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
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
        assert {item["id"] for item in newer.json()["items"]} >= {first["id"], second["id"]}

        before_dt = datetime.fromisoformat(second["created_at"].replace("Z", "+00:00")) - timedelta(
            microseconds=1
        )
        older = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "created_before": before_dt.isoformat()},
        )
        assert older.status_code == 200
        older_ids = {item["id"] for item in older.json()["items"]}
        assert first["id"] in older_ids
        assert second["id"] not in older_ids


async def test_library_search_matches_title_hook_and_caption(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-search")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
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
        assert {item["id"] for item in title_match.json()["items"]} == {draft_a["id"]}

        hook_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": "pressing"},
        )
        assert hook_match.status_code == 200
        assert {item["id"] for item in hook_match.json()["items"]} == {draft_a["id"]}

        caption_probe = next((word for word in caption.split(" ") if len(word) > 4), caption)
        caption_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": caption_probe.lower()},
        )
        assert caption_match.status_code == 200
        assert draft_b["id"] in {item["id"] for item in caption_match.json()["items"]}

        no_match = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_id, "q": "does-not-exist"},
        )
        assert no_match.status_code == 200
        assert no_match.json()["items"] == []


async def test_library_retrieve_attaches_lineage_summary(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-lineage")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
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


async def test_library_cross_workspace_and_profile_isolation(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "library-a")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_a))
        profile_a = await create_profile(client, workspace_a, "A")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_ready_draft(
            client,
            workspace_a,
            profile_a,
            brief_a,
            title="Workspace A",
            hook="Hook A",
            body="Body A",
        )

        list_a = await client.get("/api/v1/library", params={"workspace_id": workspace_a})
        assert list_a.status_code == 200
        assert {item["id"] for item in list_a.json()["items"]} == {draft_a["id"]}

        cross_profile_filter = await client.get(
            "/api/v1/library",
            params={"workspace_id": workspace_a, "profile_id": uuid.uuid4()},
        )
        assert cross_profile_filter.status_code == 404

        workspace_b = await create_workspace(client, "library-b")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_b))
        profile_b = await create_profile(client, workspace_b, "B")
        brief_b = await create_ready_brief(client, workspace_b, profile_b)
        await create_ready_draft(
            client,
            workspace_b,
            profile_b,
            brief_b,
            title="Workspace B",
            hook="Hook B",
            body="Body B",
        )

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


async def test_library_empty_and_unknown_draft(override_get_db, db_session) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-empty")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))

        empty = await client.get("/api/v1/library", params={"workspace_id": workspace_id})
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        unknown = await client.get(
            f"/api/v1/library/{uuid.uuid4()}",
            params={"workspace_id": workspace_id},
        )
        assert unknown.status_code == 404


async def test_library_default_view_is_cached_and_invalidated_on_create(
    override_get_db, _fake_cache_redis, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "library-cache")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        first = await create_ready_draft(
            client, workspace_id, profile_id, brief_id, title="One", hook="One", body="One"
        )

        first_view = await client.get("/api/v1/library", params={"workspace_id": workspace_id})
        assert first_view.status_code == 200
        assert {item["id"] for item in first_view.json()["items"]} == {first["id"]}

        cache_key = f"workspace:{workspace_id}:library:default:page_size=20"
        cached_raw = await _fake_cache_redis.get(cache_key)
        assert cached_raw is not None

        second = await create_ready_draft(
            client, workspace_id, profile_id, brief_id, title="Two", hook="Two", body="Two"
        )

        # The create above must have invalidated the cached default view;
        # a stale cache would still show only `first`.
        second_view = await client.get("/api/v1/library", params={"workspace_id": workspace_id})
        assert second_view.status_code == 200
        assert {item["id"] for item in second_view.json()["items"]} == {
            first["id"],
            second["id"],
        }
