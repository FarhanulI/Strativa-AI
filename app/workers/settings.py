from arq.connections import RedisSettings

from app.core.config import settings
from app.infrastructure.jobs.worker_tasks import execute_ai_job


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


class WorkerSettings:
    """arq worker process entrypoint, run separately from the API process:

        uv run arq app.workers.settings.WorkerSettings

    `execute_ai_job` is the sole registered function — it dispatches to
    whichever handler `app.infrastructure.jobs.registry` has for a job's
    `task_type`. Product days register real handlers there; this file does
    not grow a new entry per task type.
    """

    redis_settings = get_redis_settings()
    functions: list = [execute_ai_job]
