from arq import cron
from arq.connections import RedisSettings

import app.content_intelligence.service  # noqa: F401
import app.services.intelligence_analysis  # noqa: F401
import app.services.opportunity_reasoning  # noqa: F401
from app.core.config import settings
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.platform_connections.refresh import refresh_platform_connections_cron

# Importing app.services.intelligence_analysis registers the brand/audience/
# market analysis job handlers, app.content_intelligence.service registers
# the strategic_synthesis handler, and app.services.opportunity_reasoning
# registers the opportunity_reasoning handler (see the bottom of each
# module) — the worker process never imports the API router, so these
# imports are the only thing that makes those task_types resolvable via
# get_handler() here.


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

    # Day 23: proactive platform-token refresh. A cron job rather than a
    # queued `execute_ai_job` task type because nothing submits it -- it is
    # time-driven, not request-driven, and has no per-profile job row to
    # track. Every 15 minutes, comfortably inside the default 1-hour
    # `platform_connection_refresh_threshold_seconds`, so a near-expiry
    # token gets several refresh attempts before it can actually lapse.
    cron_jobs: list = [
        cron(refresh_platform_connections_cron, minute={0, 15, 30, 45}, run_at_startup=False)
    ]
