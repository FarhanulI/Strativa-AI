import asyncio
import logging
import uuid as uuid_module
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.infrastructure.jobs.registry import get_handler
from app.infrastructure.jobs.service import WORKER_FUNCTION_NAME
from app.infrastructure.ratelimit.errors import RateLimitDeferredError
from app.models.ai_job import AIJob, JobStatus
from app.repositories.ai_job import AIJobRepository

logger = logging.getLogger(__name__)


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff: base * 2^(attempt - 1), attempt is 1-indexed."""
    return settings.job_retry_backoff_base_seconds * (2 ** (attempt - 1))


async def execute_ai_job(ctx: dict[str, Any], job_id: str, payload: dict[str, Any]) -> None:
    """arq worker entrypoint. Runs in the worker process, so it opens its own
    DB session rather than reusing a request-scoped one.

    Per docs/product/product-architecture.md "AI Execution and Job Control":
    per-task timeout, bounded retry with backoff, and durable status/failure
    visibility. No product task type is registered yet (Day 15 is pure
    infrastructure) — only the `infrastructure.echo` placeholder handler
    exists, exercised by tests.
    """
    async with async_session_factory() as session:
        repository = AIJobRepository(session)
        job = await repository.get_by_id(UUID(job_id))
        if job is None:
            logger.warning("execute_ai_job: job %s not found", job_id)
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.attempts += 1
        await repository.update(job)
        await session.commit()

        try:
            handler = get_handler(job.task_type)
            result = await asyncio.wait_for(handler(payload), timeout=settings.job_timeout_seconds)
        except TimeoutError:
            await _handle_failure(
                ctx, session, repository, job, payload, error="job timed out", timed_out=True
            )
            return
        except RateLimitDeferredError as rate_limit_error:
            await _handle_rate_limit_deferral(
                ctx, session, repository, job, payload, rate_limit_error
            )
            return
        except Exception as exc:  # noqa: BLE001 - any handler failure must be captured, not raised
            await _handle_failure(ctx, session, repository, job, payload, error=str(exc))
            return

        job.status = JobStatus.SUCCEEDED
        job.result_ref = f"jobs/{job.id}/result"
        job.finished_at = datetime.now(UTC)
        await repository.update(job)
        await session.commit()
        return result


async def _handle_failure(
    ctx: dict[str, Any],
    session: AsyncSession,
    repository: AIJobRepository,
    job: AIJob,
    payload: dict[str, Any],
    error: str,
    timed_out: bool = False,
) -> None:
    job.error = error[:2000]

    if job.attempts < settings.job_max_attempts:
        job.status = JobStatus.QUEUED
        await repository.update(job)
        await session.commit()

        redis = ctx.get("redis")
        if redis is not None:
            await redis.enqueue_job(
                WORKER_FUNCTION_NAME,
                str(job.id),
                payload,
                _job_id=f"{job.id}:{job.attempts}",
                _defer_by=_backoff_seconds(job.attempts),
            )
        return

    job.status = JobStatus.TIMED_OUT if timed_out else JobStatus.FAILED
    job.finished_at = datetime.now(UTC)
    await repository.update(job)
    await session.commit()


async def _handle_rate_limit_deferral(
    ctx: dict[str, Any],
    session: AsyncSession,
    repository: AIJobRepository,
    job: AIJob,
    payload: dict[str, Any],
    error: RateLimitDeferredError,
) -> None:
    """A rate limit, unlike a handler failure, is not a reason to fail or
    drop the job -- it just means "not yet". The attempt this call counted
    at the top of `execute_ai_job` is undone (rate limiting is not a real
    execution attempt against `job_max_attempts`), the job stays queued, and
    it's requeued to run again once the window has room.
    """
    job.attempts = max(0, job.attempts - 1)
    job.status = JobStatus.QUEUED
    await repository.update(job)
    await session.commit()

    redis = ctx.get("redis")
    if redis is not None:
        await redis.enqueue_job(
            WORKER_FUNCTION_NAME,
            str(job.id),
            payload,
            _job_id=f"{job.id}:ratelimit:{uuid_module.uuid4().hex[:8]}",
            _defer_by=error.retry_after_seconds,
        )
