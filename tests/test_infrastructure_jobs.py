import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.jobs.registry import get_handler, register_handler
from app.infrastructure.jobs.service import submit_job
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.models.ai_job import JobStatus
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace
from app.repositories.ai_job import AIJobRepository


@pytest.fixture(autouse=True)
def _use_test_session_for_worker(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession):
    """`execute_ai_job` runs in a separate worker process in production and
    opens its own session via `async_session_factory`. Point that name at
    the shared test session instead of the real (Postgres) factory, the same
    way `tests/conftest.py` already does for the request-scoped dependency.
    """

    @asynccontextmanager
    async def _factory():
        yield db_session

    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.async_session_factory", _factory)


async def _create_profile(session: AsyncSession) -> ContentProfile:
    workspace = Workspace(name="Infra Test", slug=f"infra-test-{uuid.uuid4().hex[:8]}")
    session.add(workspace)
    await session.flush()

    profile = ContentProfile(
        workspace_id=workspace.id, type=ContentProfileType.CREATOR, name="Test Creator"
    )
    session.add(profile)
    await session.flush()
    return profile


async def test_submit_job_creates_queued_row_and_enqueues(db_session: AsyncSession) -> None:
    profile = await _create_profile(db_session)
    arq_pool = AsyncMock()

    job = await submit_job(
        db_session, arq_pool, "infrastructure.echo", profile.id, {"hello": "world"}
    )
    await db_session.commit()

    assert job.status == JobStatus.QUEUED
    assert job.attempts == 0
    arq_pool.enqueue_job.assert_awaited_once_with(
        "execute_ai_job", str(job.id), {"hello": "world"}, _job_id=str(job.id)
    )


async def test_execute_ai_job_success_marks_succeeded(db_session: AsyncSession) -> None:
    profile = await _create_profile(db_session)
    arq_pool = AsyncMock()
    job = await submit_job(db_session, arq_pool, "infrastructure.echo", profile.id, {"a": 1})
    await db_session.commit()

    await execute_ai_job({"redis": arq_pool}, str(job.id), {"a": 1})

    repository = AIJobRepository(db_session)
    refreshed = await repository.get_by_id(job.id)
    assert refreshed.status == JobStatus.SUCCEEDED
    assert refreshed.attempts == 1
    assert refreshed.result_ref == f"jobs/{job.id}/result"
    assert refreshed.finished_at is not None


async def test_execute_ai_job_forced_failure_retries_then_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _always_fails(payload: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("boom")

    register_handler("infrastructure.always_fails", _always_fails)
    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.settings.job_max_attempts", 2)
    monkeypatch.setattr(
        "app.infrastructure.jobs.worker_tasks.settings.job_retry_backoff_base_seconds", 0
    )

    profile = await _create_profile(db_session)
    arq_pool = AsyncMock()
    job = await submit_job(db_session, arq_pool, "infrastructure.always_fails", profile.id, {})
    await db_session.commit()

    ctx = {"redis": arq_pool}

    # Attempt 1: retried (attempts < max_attempts) — re-enqueued for later.
    await execute_ai_job(ctx, str(job.id), {})
    repository = AIJobRepository(db_session)
    after_first = await repository.get_by_id(job.id)
    assert after_first.status == JobStatus.QUEUED
    assert after_first.attempts == 1
    assert after_first.error == "boom"
    arq_pool.enqueue_job.assert_awaited_with(
        "execute_ai_job", str(job.id), {}, _job_id=f"{job.id}:1", _defer_by=0
    )

    # Attempt 2: exhausts max_attempts — terminal failure, no further enqueue.
    enqueue_calls_before = arq_pool.enqueue_job.await_count
    await execute_ai_job(ctx, str(job.id), {})
    after_second = await repository.get_by_id(job.id)
    assert after_second.status == JobStatus.FAILED
    assert after_second.attempts == 2
    assert after_second.finished_at is not None
    assert arq_pool.enqueue_job.await_count == enqueue_calls_before


async def test_execute_ai_job_timeout_marks_timed_out_after_max_attempts(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    async def _hangs(payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(10)
        return {}

    register_handler("infrastructure.hangs", _hangs)
    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.settings.job_timeout_seconds", 0.05)
    monkeypatch.setattr("app.infrastructure.jobs.worker_tasks.settings.job_max_attempts", 1)

    profile = await _create_profile(db_session)
    arq_pool = AsyncMock()
    job = await submit_job(db_session, arq_pool, "infrastructure.hangs", profile.id, {})
    await db_session.commit()

    await execute_ai_job({"redis": arq_pool}, str(job.id), {})

    repository = AIJobRepository(db_session)
    refreshed = await repository.get_by_id(job.id)
    assert refreshed.status == JobStatus.TIMED_OUT
    assert refreshed.attempts == 1


def test_get_handler_raises_for_unknown_task_type() -> None:
    with pytest.raises(KeyError):
        get_handler("nonexistent.task.type")
