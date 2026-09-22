import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.main import app
from app.models.ai_job import JobStatus
from app.models.workspace import Workspace
from app.repositories.ai_job import AIJobRepository
from app.services.content_performance import (
    ContentPerformanceService,
    DuplicateReportingPeriodError,
)
from tests.conftest import _test_engine, authenticate_as_workspace_owner
from tests.test_content_briefs import create_profile, create_workspace
from tests.test_content_drafts import create_ready_brief
from tests.test_published_content import authed_workspace, create_approved_draft


@pytest.fixture(autouse=True)
def _use_test_session_for_worker(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession):
    @asynccontextmanager
    async def _factory():
        yield db_session

    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.async_session_factory", _factory)
    monkeypatch.setattr("app.services.content_performance.async_session_factory", _factory)


async def create_published_content(
    client: AsyncClient, db_session: AsyncSession, workspace_id: str, profile_id: str, title: str
) -> dict:
    brief_id = await create_ready_brief(client, workspace_id, profile_id)
    draft = await create_approved_draft(client, workspace_id, profile_id, brief_id, title)
    response = await client.post(
        f"/api/v1/profiles/{profile_id}/drafts/{draft['id']}/publish",
        params={"workspace_id": workspace_id},
        json={"external_url": f"https://example.com/post/{title}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


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

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            pending = await client.post(
                f"/api/v1/profiles/{profile_id}/performance/{current['id']}/analyze",
                params={"workspace_id": workspace_id},
            )
            assert pending.status_code == 202, pending.text
            assert pending.json()["status"] == "pending"
            job_id = arq_pool.enqueue_job.await_args.args[1]
            payload = arq_pool.enqueue_job.await_args.args[2]
            await execute_ai_job({"redis": arq_pool}, job_id, payload)
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)

        fetched = await client.get(
            f"/api/v1/profiles/{profile_id}/performance/{current['id']}",
            params={"workspace_id": workspace_id},
        )
        assert fetched.status_code == 200
        service = ContentPerformanceService(db_session)
        analysis = await service.repository.get(uuid.UUID(profile_id), uuid.UUID(current["id"]))
        data = analysis.analysis
        assert data.baseline_available is True
        assert data.comparables_count == 3
        assert data.performance_classification == "strong"
        assert data.evidence["metrics"]["engagement_rate"]["relative"] == 2.3333333333333335


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


async def test_submit_metrics_rejects_unowned_published_content(
    override_get_db, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "metrics-owner")
        profile_id = await create_profile(client, workspace_id, "Creator")
        published = await create_published_content(
            client, db_session, workspace_id, profile_id, "Alpha"
        )

        other_workspace_id = await create_workspace(client, "metrics-other")
        await authenticate_as_workspace_owner(client, db_session, uuid.UUID(other_workspace_id))
        other_profile_id = await create_profile(client, other_workspace_id, "Other creator")

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            response = await client.post(
                f"/api/v1/profiles/{other_profile_id}/published/{published['id']}/metrics",
                params={"workspace_id": other_workspace_id},
                json={"reporting_period": "2026-01-01", "views": 100, "likes": 10},
            )
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)
        assert response.status_code == 404


async def test_submit_metrics_owned_published_content_enqueues_job(
    override_get_db, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "metrics-owned")
        profile_id = await create_profile(client, workspace_id, "Creator")
        published = await create_published_content(
            client, db_session, workspace_id, profile_id, "Alpha"
        )

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            response = await client.post(
                f"/api/v1/profiles/{profile_id}/published/{published['id']}/metrics",
                params={"workspace_id": workspace_id},
                json={
                    "reporting_period": "2026-01-01",
                    "views": 1000,
                    "reach": 800,
                    "likes": 100,
                    "comments": 10,
                    "shares": 5,
                    "saves": 3,
                },
            )
            assert response.status_code == 202, response.text
            data = response.json()
            assert data["status"] == "pending"
            content_performance_id = data["content_performance_id"]
            job_id = arq_pool.enqueue_job.await_args.args[1]
            payload = arq_pool.enqueue_job.await_args.args[2]
            assert payload["content_performance_id"] == content_performance_id
            await execute_ai_job({"redis": arq_pool}, job_id, payload)
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)

        repository = AIJobRepository(db_session)
        job = await repository.get_by_id(uuid.UUID(job_id))
        assert job.status == JobStatus.SUCCEEDED

        service = ContentPerformanceService(db_session)
        record = await service.repository.get(
            uuid.UUID(profile_id), uuid.UUID(content_performance_id)
        )
        assert record.published_content_id == uuid.UUID(published["id"])
        assert record.reporting_period.isoformat() == "2026-01-01"
        assert record.analysis is not None


async def test_submit_metrics_duplicate_reporting_period_conflicts(
    override_get_db, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "metrics-dup")
        profile_id = await create_profile(client, workspace_id, "Creator")
        published = await create_published_content(
            client, db_session, workspace_id, profile_id, "Alpha"
        )

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            first = await client.post(
                f"/api/v1/profiles/{profile_id}/published/{published['id']}/metrics",
                params={"workspace_id": workspace_id},
                json={"reporting_period": "2026-01-01", "views": 100, "likes": 10},
            )
            assert first.status_code == 202, first.text

            second = await client.post(
                f"/api/v1/profiles/{profile_id}/published/{published['id']}/metrics",
                params={"workspace_id": workspace_id},
                json={"reporting_period": "2026-01-01", "views": 200, "likes": 20},
            )
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)
        assert second.status_code == 409


async def test_concurrent_duplicate_reporting_period_exactly_one_succeeds() -> None:
    """DB-level unique constraint, not an application-level pre-check, must
    be what prevents a race between two concurrent submissions for the same
    (published_content_id, reporting_period).

    Unlike every other test in this suite, this one deliberately opts out of
    the standard SAVEPOINT-per-test isolation (`tests/conftest.py`'s
    `db_session_factory`): that pattern binds every session in a test to one
    shared connection/outer transaction, so a second, genuinely independent
    connection can never see the first's uncommitted writes -- which would
    make this race meaningless (there'd be nothing for the unique constraint
    to arbitrate between). This test instead uses real, separately-connected,
    actually-committing sessions throughout -- setup included -- and cleans
    up its own rows afterward, since nothing here rolls back automatically.
    """
    real_session_factory = async_sessionmaker(
        bind=_test_engine, expire_on_commit=False, autoflush=False
    )

    async def _override_get_db():
        async with real_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db
    workspace_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with real_session_factory() as setup_session:
                workspace_id = await authed_workspace(client, setup_session, "metrics-race")
            profile_id = await create_profile(client, workspace_id, "Creator")
            published = await create_published_content(
                client, None, workspace_id, profile_id, "Alpha"
            )

        arq_pool = AsyncMock()

        async def submit() -> bool:
            async with real_session_factory() as session:
                service = ContentPerformanceService(session)
                try:
                    await service.submit_metrics(
                        uuid.UUID(profile_id),
                        uuid.UUID(workspace_id),
                        uuid.UUID(published["id"]),
                        arq_pool,
                        reporting_period=__import__("datetime").date(2026, 1, 1),
                        views=100,
                        likes=10,
                    )
                except DuplicateReportingPeriodError:
                    return False
                return True

        results = await asyncio.gather(submit(), submit())
        assert sorted(results) == [False, True]
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        if workspace_id is not None:
            async with real_session_factory() as cleanup_session:
                workspace = await cleanup_session.get(Workspace, uuid.UUID(workspace_id))
                if workspace is not None:
                    await cleanup_session.delete(workspace)
                    await cleanup_session.commit()


async def test_baseline_comparison_against_real_published_content_history(
    override_get_db, db_session
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await authed_workspace(client, db_session, "metrics-baseline")
        profile_id = await create_profile(client, workspace_id, "Creator")

        arq_pool = AsyncMock()
        app.dependency_overrides[get_arq_pool] = lambda: arq_pool
        try:
            job_id = None
            payload = None
            for index, likes in enumerate((10, 20, 30, 60)):
                published = await create_published_content(
                    client, db_session, workspace_id, profile_id, f"Item-{index}"
                )
                response = await client.post(
                    f"/api/v1/profiles/{profile_id}/published/{published['id']}/metrics",
                    params={"workspace_id": workspace_id},
                    json={
                        "reporting_period": "2026-01-01",
                        "views": 100,
                        "reach": 100,
                        "likes": likes,
                        "shares": 10,
                    },
                )
                assert response.status_code == 202, response.text
                data = response.json()
                job_id = arq_pool.enqueue_job.await_args.args[1]
                payload = arq_pool.enqueue_job.await_args.args[2]
                content_performance_id = data["content_performance_id"]
            await execute_ai_job({"redis": arq_pool}, job_id, payload)
        finally:
            app.dependency_overrides.pop(get_arq_pool, None)

        service = ContentPerformanceService(db_session)
        record = await service.repository.get(
            uuid.UUID(profile_id), uuid.UUID(content_performance_id)
        )
        analysis = record.analysis
        assert analysis.baseline_available is True
        assert analysis.comparables_count == 3
        assert analysis.performance_classification == "strong"
