"""Due-item promotion and stuck-row recovery, run as Day 15 registered
periodic jobs (arq `cron_jobs` -- see `app/workers/settings.py`), never as a
FastAPI startup-event `asyncio.create_task` poller. That distinction matters:
an in-process asyncio task lives and dies with one API process, gives no
visibility into whether it's actually running, and (before this day) was the
literal reason `PublishedContentService.promote_due`'s atomic claim was the
*only* thing standing between two API instances and a double-publish. arq's
worker process is a first-class, independently deployable/scalable component
of the platform's existing job infrastructure.

Both jobs open their own session -- this runs in the arq worker process,
which has no request-scoped session, matching the Day 23
`refresh_platform_connections_cron` pattern.
"""

import logging
from typing import Any

from app.core.database import async_session_factory
from app.infrastructure.locks.service import try_lock
from app.infrastructure.redis_client import get_redis
from app.services.published_content import PublishedContentService

logger = logging.getLogger(__name__)


async def promote_due_publishes() -> dict[str, int]:
    """Claim and call every due scheduled publish.

    `PublishedContentService.promote_due`'s atomic `UPDATE ... WHERE
    status = 'scheduled' ... RETURNING` is what actually prevents a row
    being claimed twice under N concurrent worker instances -- the
    `DistributedLock` here is only a performance optimization (skips a
    worker doing a redundant claim query on a tick another worker is
    already mid-way through), never a substitute for it. If the lock isn't
    acquired, this tick simply does nothing; the atomic claim means that is
    always safe.
    """
    redis = get_redis()
    async with try_lock(redis, "publish-promotion:tick") as acquired:
        if not acquired:
            return {"promoted": 0}

        async with async_session_factory() as session:
            service = PublishedContentService(session)
            promoted = await service.promote_due()
            await session.commit()

    if promoted:
        logger.info("publish_promotion.tick", extra={"promoted": len(promoted)})
    return {"promoted": len(promoted)}


async def promote_due_publishes_cron(ctx: dict[str, Any]) -> dict[str, int]:
    """arq cron entrypoint (arq passes a `ctx` this job doesn't need).

    Cadence tradeoff: arq cron fires on second-of-minute marks, not an
    arbitrary interval, so `publish_promotion_interval_seconds` (default 30,
    must evenly divide 60) is expanded into that many marks within each
    minute by `app.workers.settings`. A shorter interval means scheduled
    publishes fire closer to their `scheduled_at`, at the cost of an extra
    claim-query poll per worker per tick; 30s keeps that cost low while
    keeping publish latency well under a minute for the common case.
    """
    return await promote_due_publishes()


async def recover_stuck_publishes() -> dict[str, int]:
    """Move any row stuck in `publishing` past the timeout to `failed`.

    A row can only be stuck here if a worker crashed/was killed after
    claiming it but before resolving it to a terminal status --
    `promote_due` itself always finishes a claimed row within the same
    tick, so this sweep is a safety net, not the normal path.
    """
    async with async_session_factory() as session:
        service = PublishedContentService(session)
        recovered = await service.recover_stuck_publishing()
        await session.commit()

    if recovered:
        logger.warning(
            "publish_promotion.recovered_stuck_publishing", extra={"count": len(recovered)}
        )
    return {"recovered": len(recovered)}


async def recover_stuck_publishes_cron(ctx: dict[str, Any]) -> dict[str, int]:
    """arq cron entrypoint. Runs far less often than promotion itself --
    `settings.publish_stuck_recovery_interval_minutes` -- since it only
    matters after a worker crash, not on the normal happy path.
    """
    return await recover_stuck_publishes()
