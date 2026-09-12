import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.published_content import PublishStatus
from app.services.published_content import PublishedContentService
from tests.test_content_briefs import create_profile, create_workspace
from tests.test_content_drafts import create_ready_brief
from tests.test_content_library import create_ready_draft


async def create_approved_draft(
    client: AsyncClient, workspace_id: str, profile_id: str, brief_id: str, title: str
) -> dict:
    draft = await create_ready_draft(
        client,
        workspace_id,
        profile_id,
        brief_id,
        title=title,
        hook=f"{title} hook",
        body=f"{title} body",
    )
    ready = await client.patch(
        f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}",
        params={"workspace_id": workspace_id},
        json={"status": "ready"},
    )
    assert ready.status_code == 200, ready.text
    approved = await client.patch(
        f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}",
        params={"workspace_id": workspace_id},
        json={"status": "approved"},
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


async def test_publish_approved_draft_creates_record_without_mutating_draft(
    override_get_db,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "publish-approved")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Alpha")

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={"external_url": "https://example.com/post/1"},
        )
        assert response.status_code == 201, response.text
        published = response.json()
        assert published["draft_id"] == draft["id"]
        assert published["profile_id"] == profile_id
        assert published["platform"] == draft["platform"]
        assert published["external_url"] == "https://example.com/post/1"
        assert published["publish_method"] == "manual"
        assert published["status"] == "published"

        unchanged = await client.get(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}",
            params={"workspace_id": workspace_id},
        )
        assert unchanged.status_code == 200
        unchanged_data = unchanged.json()
        assert unchanged_data["status"] == "approved"
        assert unchanged_data["hook"] == draft["hook"]
        assert unchanged_data["body"] == draft["body"]
        assert unchanged_data["caption"] == draft["caption"]


async def test_publish_ineligible_status_draft_rejected(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "publish-ineligible")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        transitions = {
            "draft": [],
            "archived": ["ready", "approved", "archived"],
        }
        for target_status, path in transitions.items():
            draft = await create_ready_draft(
                client,
                workspace_id,
                profile_id,
                brief_id,
                title=f"Status {target_status}",
                hook="hook",
                body="body",
            )
            for step in path:
                set_status = await client.patch(
                    f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}",
                    params={"workspace_id": workspace_id},
                    json={"status": step},
                )
                assert set_status.status_code == 200, set_status.text

            response = await client.post(
                f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
                params={"workspace_id": workspace_id},
                json={},
            )
            assert response.status_code == 409, response.text

            listed = await client.get(
                f"/api/v1/profiles/{profile_id}/published",
                params={"workspace_id": workspace_id},
            )
            assert listed.status_code == 200
            assert draft["id"] not in {item["draft_id"] for item in listed.json()}


async def test_publish_ready_draft_is_eligible(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "publish-ready")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        draft = await create_ready_draft(
            client, workspace_id, profile_id, brief_id, title="Ready", hook="hook", body="body"
        )
        ready = await client.patch(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}",
            params={"workspace_id": workspace_id},
            json={"status": "ready"},
        )
        assert ready.status_code == 200, ready.text

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "published"


async def test_publish_ownership_failures_return_404(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "publish-owner-a")
        workspace_b = await create_workspace(client, "publish-owner-b")
        profile_a = await create_profile(client, workspace_a, "A")
        profile_b = await create_profile(client, workspace_b, "B")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_approved_draft(client, workspace_a, profile_a, brief_a, "Owned")

        missing_draft = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{uuid.uuid4()}/publish",
            params={"workspace_id": workspace_a},
            json={},
        )
        assert missing_draft.status_code == 404

        wrong_profile = await client.post(
            f"/api/v1/profiles/{profile_b}/drafts/{draft_a['id']}/publish",
            params={"workspace_id": workspace_b},
            json={},
        )
        assert wrong_profile.status_code == 404

        wrong_workspace = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a['id']}/publish",
            params={"workspace_id": workspace_b},
            json={},
        )
        assert wrong_workspace.status_code == 404


async def test_list_published_content_filters_by_platform_and_status(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "publish-list")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        draft_one = await create_approved_draft(client, workspace_id, profile_id, brief_id, "One")
        draft_two = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Two")

        first = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_one['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert first.status_code == 201
        second = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft_two['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert second.status_code == 201

        by_platform = await client.get(
            f"/api/v1/profiles/{profile_id}/published",
            params={"workspace_id": workspace_id, "platform": draft_one["platform"]},
        )
        assert by_platform.status_code == 200
        assert len(by_platform.json()) == 2

        by_status = await client.get(
            f"/api/v1/profiles/{profile_id}/published",
            params={"workspace_id": workspace_id, "status": "published"},
        )
        assert by_status.status_code == 200
        assert len(by_status.json()) == 2

        by_missing_status = await client.get(
            f"/api/v1/profiles/{profile_id}/published",
            params={"workspace_id": workspace_id, "status": "retracted"},
        )
        assert by_missing_status.status_code == 200
        assert by_missing_status.json() == []


async def test_get_published_content_returns_lineage(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "publish-lineage")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Lineage")

        published_response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert published_response.status_code == 201
        published_id = published_response.json()["id"]

        response = await client.get(
            f"/api/v1/profiles/{profile_id}/published/{published_id}",
            params={"workspace_id": workspace_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["published"]["id"] == published_id
        assert data["draft"]["id"] == draft["id"]
        assert data["brief"]["id"] == brief_id
        assert data["opportunity"]["id"]


async def test_get_published_content_cross_workspace_and_profile_isolation(
    override_get_db,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "publish-isolation-a")
        workspace_b = await create_workspace(client, "publish-isolation-b")
        profile_a = await create_profile(client, workspace_a, "A")
        profile_b = await create_profile(client, workspace_b, "B")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_approved_draft(client, workspace_a, profile_a, brief_a, "A item")

        published = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a['id']}/publish",
            params={"workspace_id": workspace_a},
            json={},
        )
        assert published.status_code == 201
        published_id = published.json()["id"]

        cross_workspace = await client.get(
            f"/api/v1/profiles/{profile_a}/published/{published_id}",
            params={"workspace_id": workspace_b},
        )
        assert cross_workspace.status_code == 404

        cross_profile = await client.get(
            f"/api/v1/profiles/{profile_b}/published/{published_id}",
            params={"workspace_id": workspace_a},
        )
        assert cross_profile.status_code == 404

        cross_workspace_list = await client.get(
            f"/api/v1/profiles/{profile_a}/published",
            params={"workspace_id": workspace_b},
        )
        assert cross_workspace_list.status_code == 404


async def test_schedule_approved_draft_creates_scheduled_record(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "schedule-create")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Sched")

        scheduled_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": scheduled_at},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "scheduled"
        assert data["published_at"] is None
        assert data["scheduled_at"] is not None
        assert data["draft_id"] == draft["id"]


async def test_schedule_rejects_past_time_and_ineligible_draft(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "schedule-invalid")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Past")

        past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        past_response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": past_time},
        )
        assert past_response.status_code == 422, past_response.text

        # Still in "draft" status — neither ready nor approved, so ineligible.
        ineligible_draft = await create_ready_draft(
            client,
            workspace_id,
            profile_id,
            brief_id,
            title="Not ready",
            hook="hook",
            body="body",
        )
        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        ineligible_response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{ineligible_draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": future_time},
        )
        assert ineligible_response.status_code == 409, ineligible_response.text


async def test_promote_due_publishes_scheduled_items_and_leaves_future_ones(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "schedule-promote")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)

        due_draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Due")
        future_draft = await create_approved_draft(
            client, workspace_id, profile_id, brief_id, "Future"
        )

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        far_future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

        due_scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{due_draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": near_future},
        )
        assert due_scheduled.status_code == 201
        due_id = due_scheduled.json()["id"]

        future_scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{future_draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": far_future},
        )
        assert future_scheduled.status_code == 201
        future_id = future_scheduled.json()["id"]

        service = PublishedContentService(db_session)
        promotion_time = datetime.now(UTC) + timedelta(minutes=2)
        promoted = await service.promote_due(now=promotion_time)
        assert {str(item.id) for item in promoted} == {due_id}
        assert promoted[0].status == PublishStatus.PUBLISHED
        # SQLite's UPDATE...RETURNING drops tzinfo on round-trip; the stored
        # instant is still correct, so compare on a normalized basis.
        published_at = promoted[0].published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        assert published_at == promotion_time

        still_scheduled = await client.get(
            f"/api/v1/profiles/{profile_id}/published/{future_id}",
            params={"workspace_id": workspace_id},
        )
        assert still_scheduled.status_code == 200
        assert still_scheduled.json()["published"]["status"] == "scheduled"

        promoted_item = await client.get(
            f"/api/v1/profiles/{profile_id}/published/{due_id}",
            params={"workspace_id": workspace_id},
        )
        assert promoted_item.status_code == 200
        assert promoted_item.json()["published"]["status"] == "published"


async def test_cancel_scheduled_publish_succeeds_and_is_excluded_from_promotion(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "schedule-cancel")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Cancel")

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": near_future},
        )
        assert scheduled.status_code == 201
        published_id = scheduled.json()["id"]

        cancelled = await client.post(
            f"/api/v1/profiles/{profile_id}/published/{published_id}/cancel",
            params={"workspace_id": workspace_id},
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"

        service = PublishedContentService(db_session)
        promotion_time = datetime.now(UTC) + timedelta(minutes=2)
        promoted = await service.promote_due(now=promotion_time)
        assert published_id not in {str(item.id) for item in promoted}

        unchanged = await client.get(
            f"/api/v1/profiles/{profile_id}/published/{published_id}",
            params={"workspace_id": workspace_id},
        )
        assert unchanged.status_code == 200
        assert unchanged.json()["published"]["status"] == "cancelled"


async def test_cancel_non_scheduled_publish_rejected(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "cancel-ineligible")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Direct")

        published = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert published.status_code == 201
        published_id = published.json()["id"]

        cancel_attempt = await client.post(
            f"/api/v1/profiles/{profile_id}/published/{published_id}/cancel",
            params={"workspace_id": workspace_id},
        )
        assert cancel_attempt.status_code == 409, cancel_attempt.text


async def test_cancel_scheduled_publish_ownership_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await create_workspace(client, "cancel-owner-a")
        workspace_b = await create_workspace(client, "cancel-owner-b")
        profile_a = await create_profile(client, workspace_a, "A")
        profile_b = await create_profile(client, workspace_b, "B")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_approved_draft(client, workspace_a, profile_a, brief_a, "Isolate")

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        scheduled = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a['id']}/schedule",
            params={"workspace_id": workspace_a},
            json={"scheduled_at": near_future},
        )
        assert scheduled.status_code == 201
        published_id = scheduled.json()["id"]

        wrong_profile = await client.post(
            f"/api/v1/profiles/{profile_b}/published/{published_id}/cancel",
            params={"workspace_id": workspace_b},
        )
        assert wrong_profile.status_code == 404

        wrong_workspace = await client.post(
            f"/api/v1/profiles/{profile_a}/published/{published_id}/cancel",
            params={"workspace_id": workspace_b},
        )
        assert wrong_workspace.status_code == 404


async def test_promote_due_atomic_claim_prevents_double_processing(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await create_workspace(client, "schedule-atomic")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Atomic")

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": near_future},
        )
        assert scheduled.status_code == 201
        published_id = scheduled.json()["id"]

        service = PublishedContentService(db_session)
        promotion_time = datetime.now(UTC) + timedelta(minutes=2)

        first_pass = await service.promote_due(now=promotion_time)
        assert {str(item.id) for item in first_pass} == {published_id}

        # A second call standing in for a second app instance's poller tick
        # hitting the same due window must not reclaim the already-promoted row.
        second_pass = await service.promote_due(now=promotion_time)
        assert second_pass == []
