from typing import Any
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJob
from app.repositories.ai_job import AIJobRepository

WORKER_FUNCTION_NAME = "execute_ai_job"


async def submit_job(
    session: AsyncSession,
    arq_pool: ArqRedis,
    task_type: str,
    profile_id: UUID,
    payload: dict[str, Any] | None = None,
) -> AIJob:
    """Create the durable status row and enqueue the arq job in one call.

    Uses the job row's own id as the arq `_job_id` so arq's own dedup
    (an enqueue with a `_job_id` already in flight is a no-op) lines up with
    our row-per-submission model. Callers own the transaction boundary —
    this flushes but does not commit, per the project's "transactions are
    owned at the boundary" convention; commit before or alongside enqueueing
    only once the caller's unit of work is ready to finish.
    """
    repository = AIJobRepository(session)
    job = await repository.create(AIJob(task_type=task_type, profile_id=profile_id))

    await arq_pool.enqueue_job(
        WORKER_FUNCTION_NAME,
        str(job.id),
        payload or {},
        _job_id=str(job.id),
    )
    return job
