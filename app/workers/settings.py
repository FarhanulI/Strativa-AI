from arq.connections import RedisSettings

import app.services.intelligence_analysis  # noqa: F401
from app.core.config import settings
from app.infrastructure.jobs.worker_tasks import execute_ai_job

# Importing app.services.intelligence_analysis registers the brand/audience/
# market analysis job handlers (see the bottom of that module) — the worker
# process never imports the API router, so this import is the only thing
# that makes those task_types resolvable via get_handler() here.


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
