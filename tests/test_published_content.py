import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.content_draft import ContentDraft
from app.models.published_content import PublishedContent, PublishStatus
from app.platform_connections import adapters as adapters_module
from app.platform_connections.crypto import encrypt_token
from app.platform_connections.models import ConnectionStatus, PlatformConnection, SocialPlatform
from app.services.published_content import PublishedContentService
from tests.conftest import authenticate_as_workspace_owner
from tests.test_content_briefs import create_profile, create_workspace
from tests.test_content_drafts import create_ready_brief
from tests.test_content_library import create_ready_draft


async def create_approved_draft(
    client: AsyncClient,
    workspace_id: str,
    profile_id: str,
    brief_id: str,
    title: str,
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


async def create_approved_draft_on_platform(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_id: str,
    profile_id: str,
    brief_id: str,
    title: str,
    platform: str,
) -> dict:
    """A draft whose `platform` matches a real (Day 23) connection-required
    platform. Drafts inherit `platform` from their brief's
    `recommended_platform` (which defaults to "other" -- see
    `app.services.brief.composer`), so it's overwritten directly for tests
    that need a specific connection-required platform.
    """
    draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, title)
    result = await db_session.get(ContentDraft, uuid.UUID(draft["id"]))
    result.platform = platform
    await db_session.commit()
    await db_session.refresh(result)
    draft["platform"] = platform
    return draft


async def seed_connection(
    db_session: AsyncSession,
    *,
    workspace_id: str,
    profile_id: str,
    platform: SocialPlatform,
    status: ConnectionStatus = ConnectionStatus.CONNECTED,
    external_account_id: str = "destination-1",
) -> PlatformConnection:
    connection = PlatformConnection(
        workspace_id=uuid.UUID(workspace_id),
        profile_id=uuid.UUID(profile_id),
        platform=platform,
        external_account_id=external_account_id,
        external_account_name="Test destination",
        access_token_encrypted=encrypt_token("STORED-ACCESS-TOKEN"),
        status=status,
    )
    db_session.add(connection)
    await db_session.commit()
    await db_session.refresh(connection)
    return connection


def fake_facebook_client(*, post_id: str = "PAGE_123_POST_456", status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/feed")
        if status_code != 200:
            return httpx.Response(status_code, text="platform rejected the request")
        return httpx.Response(200, json={"id": post_id})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_real_publish_network(monkeypatch: pytest.MonkeyPatch):
    """Every test in this file that reaches a real adapter gets a client
    that never touches the network by default; tests exercising the
    Facebook success/failure path override this per-test.
    """
    monkeypatch.setattr(adapters_module, "build_http_client", fake_facebook_client)


async def authed_workspace(client: AsyncClient, db_session: AsyncSession, slug: str) -> str:
    workspace_id = await create_workspace(client, slug)
    await authenticate_as_workspace_owner(client, db_session, uuid.UUID(workspace_id))
    return workspace_id


async def test_publish_approved_draft_creates_record_without_mutating_draft(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-approved")
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
        assert published["platform_post_id"] is None

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


async def test_publish_ineligible_status_draft_rejected(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-ineligible")
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


async def test_publish_ready_draft_is_eligible(override_get_db, db_session: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-ready")
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


async def test_publish_ownership_failures_return_404(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await authed_workspace(client, db_session, "publish-owner-a")
        profile_a = await create_profile(client, workspace_a, "A")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_approved_draft(client, workspace_a, profile_a, brief_a, "Owned")

        missing_draft = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{uuid.uuid4()}/publish",
            params={"workspace_id": workspace_a},
            json={},
        )
        assert missing_draft.status_code == 404

        workspace_b = await authed_workspace(client, db_session, "publish-owner-b")
        profile_b = await create_profile(client, workspace_b, "B")

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


async def test_list_published_content_filters_by_platform_and_status(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-list")
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


async def test_get_published_content_returns_lineage(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-lineage")
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
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await authed_workspace(client, db_session, "publish-isolation-a")
        profile_a = await create_profile(client, workspace_a, "A")
        brief_a = await create_ready_brief(client, workspace_a, profile_a)
        draft_a = await create_approved_draft(client, workspace_a, profile_a, brief_a, "A item")

        published = await client.post(
            f"/api/v1/profiles/{profile_a}/drafts/{draft_a['id']}/publish",
            params={"workspace_id": workspace_a},
            json={},
        )
        assert published.status_code == 201
        published_id = published.json()["id"]

        workspace_b = await authed_workspace(client, db_session, "publish-isolation-b")
        profile_b = await create_profile(client, workspace_b, "B")

        cross_workspace = await client.get(
            f"/api/v1/profiles/{profile_a}/published/{published_id}",
            params={"workspace_id": workspace_b},
        )
        assert cross_workspace.status_code == 404

        cross_profile = await client.get(
            f"/api/v1/profiles/{profile_b}/published/{published_id}",
            params={"workspace_id": workspace_b},
        )
        assert cross_profile.status_code == 404

        cross_workspace_list = await client.get(
            f"/api/v1/profiles/{profile_a}/published",
            params={"workspace_id": workspace_b},
        )
        assert cross_workspace_list.status_code == 404


async def test_schedule_approved_draft_creates_scheduled_record(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "schedule-create")
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


async def test_schedule_rejects_past_time_and_ineligible_draft(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "schedule-invalid")
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
        workspace_id = await authed_workspace(client, db_session, "schedule-promote")
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
        workspace_id = await authed_workspace(client, db_session, "schedule-cancel")
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


async def test_cancel_non_scheduled_publish_rejected(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "cancel-ineligible")
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


async def test_cancel_scheduled_publish_ownership_isolation(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_a = await authed_workspace(client, db_session, "cancel-owner-a")
        profile_a = await create_profile(client, workspace_a, "A")
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

        workspace_b = await authed_workspace(client, db_session, "cancel-owner-b")
        profile_b = await create_profile(client, workspace_b, "B")

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
        workspace_id = await authed_workspace(client, db_session, "schedule-atomic")
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


async def test_atomic_claim_alone_prevents_double_claim_without_the_lock(
    override_get_db, db_session: AsyncSession
) -> None:
    """Proves the correctness claim directly, per the Day 24 spec: the
    atomic `UPDATE ... WHERE status = 'scheduled' ... RETURNING` in
    `PublishedContentRepository.claim_publishing` is what prevents a
    double-claim, not the `DistributedLock` wrapped around the cron job in
    `app.services.publish_promotion` (which `PublishedContentService`
    itself never touches). Two independent `PublishedContentService`
    instances stand in for two concurrent worker instances calling
    `claim_publishing` directly, with no lock involved anywhere in this
    call path.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "schedule-atomic-nolock")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "NoLock")

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": near_future},
        )
        assert scheduled.status_code == 201
        published_id = scheduled.json()["id"]

        promotion_time = datetime.now(UTC) + timedelta(minutes=2)
        worker_one = PublishedContentService(db_session).repository
        worker_two = PublishedContentService(db_session).repository

        claimed_by_one = await worker_one.claim_publishing(promotion_time)
        claimed_by_two = await worker_two.claim_publishing(promotion_time)

        assert {str(item.id) for item in claimed_by_one} == {published_id}
        assert claimed_by_two == []


async def test_publish_rejected_for_disconnected_platform_records_failure(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-disconnected")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, "NoConn", "facebook"
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "failed"
        assert data["publish_method"] == "api"
        assert data["published_metadata"]["failure_reason"] == "PlatformNotConnectedError"


async def test_schedule_rejected_for_disconnected_platform(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "schedule-disconnected")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, "NoConnSched", "youtube"
        )

        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": future_time},
        )
        assert response.status_code == 422, response.text
        assert "not connected" in response.json()["detail"]


async def test_schedule_accepted_once_platform_connected(
    override_get_db, db_session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "schedule-connected")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, "Conn", "facebook"
        )
        await seed_connection(
            db_session,
            workspace_id=workspace_id,
            profile_id=profile_id,
            platform=SocialPlatform.FACEBOOK,
        )

        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": future_time},
        )
        assert response.status_code == 201, response.text
        assert response.json()["publish_method"] == "api"


async def test_publish_facebook_success_records_platform_post_id(
    override_get_db, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapters_module,
        "build_http_client",
        lambda: fake_facebook_client(post_id="PAGE_1_POST_9"),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-facebook-success")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, "FbOk", "facebook"
        )
        await seed_connection(
            db_session,
            workspace_id=workspace_id,
            profile_id=profile_id,
            platform=SocialPlatform.FACEBOOK,
            external_account_id="page-1",
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "published"
        assert data["publish_method"] == "api"
        assert data["platform_post_id"] == "PAGE_1_POST_9"
        assert data["external_url"] == "https://www.facebook.com/PAGE_1_POST_9"


async def test_publish_facebook_platform_failure_marks_failed(
    override_get_db, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapters_module,
        "build_http_client",
        lambda: fake_facebook_client(status_code=500),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-facebook-failure")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, "FbFail", "facebook"
        )
        await seed_connection(
            db_session,
            workspace_id=workspace_id,
            profile_id=profile_id,
            platform=SocialPlatform.FACEBOOK,
            external_account_id="page-1",
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "failed"
        assert data["platform_post_id"] is None
        assert data["published_metadata"]["failure_reason"] == "OAuthExchangeError"


@pytest.mark.parametrize("platform", ["youtube", "instagram"])
async def test_publish_media_required_platforms_fail_without_a_network_call(
    override_get_db, db_session: AsyncSession, platform: str
) -> None:
    """YouTube/Instagram require a video/image asset ContentDraft (Day 12,
    text-only) does not produce -- a real, deterministic failure, not a
    faked success, and no network call is attempted at all (see
    `tests.test_published_content._no_real_publish_network`, which would
    assert on `/feed` if this ever tried to POST anywhere).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, f"publish-{platform}-media")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, f"{platform}-media", platform
        )
        await seed_connection(
            db_session,
            workspace_id=workspace_id,
            profile_id=profile_id,
            platform=SocialPlatform(platform),
        )

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "failed"
        assert data["published_metadata"]["failure_reason"] == "MediaRequiredError"


async def test_promote_due_calls_real_adapter_for_connected_platform(
    override_get_db, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapters_module,
        "build_http_client",
        lambda: fake_facebook_client(post_id="SCHED_POST_1"),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "schedule-real-adapter")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft_on_platform(
            client, db_session, workspace_id, profile_id, brief_id, "SchedFb", "facebook"
        )
        await seed_connection(
            db_session,
            workspace_id=workspace_id,
            profile_id=profile_id,
            platform=SocialPlatform.FACEBOOK,
        )

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": near_future},
        )
        assert scheduled.status_code == 201

        service = PublishedContentService(db_session)
        promoted = await service.promote_due(now=datetime.now(UTC) + timedelta(minutes=2))
        assert len(promoted) == 1
        assert promoted[0].status == PublishStatus.PUBLISHED
        assert promoted[0].platform_post_id == "SCHED_POST_1"


async def test_recover_stuck_publishing_moves_old_publishing_rows_to_failed(
    override_get_db, db_session: AsyncSession
) -> None:
    """Simulates a worker that claimed a row and then crashed before
    resolving it -- the only way a row can be left in `publishing`, since
    `promote_due` always resolves a claimed row within the same call.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "recover-stuck")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Stuck")

        near_future = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        scheduled = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/schedule",
            params={"workspace_id": workspace_id},
            json={"scheduled_at": near_future},
        )
        assert scheduled.status_code == 201
        published_id = scheduled.json()["id"]

        service = PublishedContentService(db_session)
        claim_time = datetime.now(UTC) + timedelta(minutes=2)
        claimed = await service.repository.claim_publishing(claim_time)
        assert {str(item.id) for item in claimed} == {published_id}

        # Not yet stuck: still well within the timeout window.
        not_yet = await service.recover_stuck_publishing(now=claim_time)
        assert not_yet == []

        far_later = claim_time + timedelta(seconds=100_000)
        recovered = await service.recover_stuck_publishing(now=far_later)
        assert {str(item.id) for item in recovered} == {published_id}
        assert recovered[0].status == PublishStatus.FAILED
        assert recovered[0].published_metadata["failure_reason"] == "stuck_publishing_timeout"


async def test_index_supports_the_claim_query(override_get_db, db_session: AsyncSession) -> None:
    """Documents the access-path index the atomic claim query relies on --
    `(status, scheduled_at)`, per the Day 24 spec. A real query-plan
    assertion needs Postgres (SQLite's planner/EXPLAIN output isn't
    representative), matching this project's established
    Postgres-vs-SQLite testing convention; this asserts the index exists on
    the model's own table_args instead.
    """
    index_names = {index.name for index in PublishedContent.__table__.indexes}
    assert "ix_published_content_status_scheduled_at" in index_names


async def test_publish_manual_unconnected_platform_still_uses_manual_adapter(
    override_get_db, db_session: AsyncSession
) -> None:
    """A draft on a platform with no real adapter (e.g. the default "other"
    from `app.services.brief.composer`) keeps using the original manual/
    no-op publish path unchanged -- no PlatformConnection is required.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "publish-manual-other")
        profile_id = await create_profile(client, workspace_id, "Creator")
        brief_id = await create_ready_brief(client, workspace_id, profile_id)
        draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, "Manual")
        assert draft["platform"] == "other"

        response = await client.post(
            f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
            params={"workspace_id": workspace_id},
            json={},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "published"
        assert data["publish_method"] == "manual"
