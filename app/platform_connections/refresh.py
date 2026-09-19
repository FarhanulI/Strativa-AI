"""Proactive token refresh, run as a Day 15 scheduled job.

A token that lapses is discovered either here, minutes before it matters,
or by the user at publish time as an opaque failure. This job exists so it
is always the former.

It runs on the Day 15 arq worker's `cron_jobs` (see
`app/workers/settings.py`) against the same Redis connection the rest of
the job infrastructure uses -- it is not a second scheduler, and (like the
Day 24 due-publish promotion job in `app.services.publish_promotion`) it is
not an in-process FastAPI-lifespan poller.

The due-item query (`status = connected AND token_expires_at <= now +
threshold`) is served by the model's `(status, token_expires_at)` composite
index.

Failure handling follows the architecture's "AI Execution and Job Control"
principle that a failure gets a durable, visible state: a connection that
cannot be refreshed is marked `status=expired` (with the reason in its
metadata) so the user can be shown "reconnect YouTube" — it is never left
looking `connected` to fail silently at publish time later.
"""

import logging
from typing import Any

from app.core.database import async_session_factory
from app.platform_connections.service import PlatformConnectionService

logger = logging.getLogger(__name__)


async def refresh_due_connections() -> dict[str, int]:
    """Refresh every near-expiry connection. Returns a small summary.

    Opens its own session: this runs in the arq worker process, which has
    no request-scoped session, matching `execute_ai_job`'s own pattern.

    One connection's failure never aborts the batch -- each is refreshed
    and committed independently, so a single bad credential can't stop
    every other workspace's tokens from being renewed.
    """
    async with async_session_factory() as session:
        service = PlatformConnectionService(session)
        due = await service.list_due_for_refresh()

        refreshed = 0
        expired = 0
        for connection in due:
            if await service.refresh_connection(connection):
                refreshed += 1
            else:
                expired += 1

    if due:
        logger.info(
            "platform_connection.refresh_batch",
            extra={"due": len(due), "refreshed": refreshed, "expired": expired},
        )
    return {"due": len(due), "refreshed": refreshed, "expired": expired}


async def refresh_platform_connections_cron(ctx: dict[str, Any]) -> dict[str, int]:
    """arq cron entrypoint (arq passes a `ctx` this job doesn't need)."""
    return await refresh_due_connections()
