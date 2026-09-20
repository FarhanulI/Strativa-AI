from arq import cron
from arq.connections import RedisSettings

import app.content_intelligence.service  # noqa: F401
import app.services.content_performance  # noqa: F401
import app.services.intelligence_analysis  # noqa: F401
import app.services.opportunity_reasoning  # noqa: F401
from app.core.config import settings
from app.infrastructure.jobs.worker_tasks import execute_ai_job
from app.learning.extraction import extract_learnings_cron
from app.platform_connections.refresh import refresh_platform_connections_cron
from app.services.publish_promotion import (
    promote_due_publishes_cron,
    recover_stuck_publishes_cron,
)

# Importing app.services.intelligence_analysis registers the brand/audience/
# market analysis job handlers, app.content_intelligence.service registers
# the strategic_synthesis handler, app.services.opportunity_reasoning
# registers the opportunity_reasoning handler, and app.services.
# content_performance registers the Day 25 performance_analysis handler
# (see the bottom of each module) — the worker process never imports the
# API router, so these imports are the only thing that makes those
# task_types resolvable via get_handler() here.


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
    #
    # Day 24: due-publish promotion and stuck-row recovery, both registered
    # here rather than as a FastAPI startup-event asyncio task (see
    # app/services/publish_promotion.py). arq cron fires on fixed
    # second/minute marks, not an arbitrary interval, so the configured
    # intervals are expanded into the marks that approximate them.
    cron_jobs: list = [
        cron(refresh_platform_connections_cron, minute={0, 15, 30, 45}, run_at_startup=False),
        cron(
            promote_due_publishes_cron,
            second=set(range(0, 60, settings.publish_promotion_interval_seconds)),
            run_at_startup=False,
        ),
        cron(
            recover_stuck_publishes_cron,
            minute=set(range(0, 60, settings.publish_stuck_recovery_interval_minutes)),
            run_at_startup=False,
        ),
        # Day 26: nightly deterministic pattern extraction (Learning
        # Engine) -- time-driven, not request-driven, so a cron job rather
        # than a queued execute_ai_job task type, matching the two entries
        # above.
        cron(
            extract_learnings_cron,
            hour={settings.learning_extraction_hour},
            minute={settings.learning_extraction_minute},
            run_at_startup=False,
        ),
    ]
