import asyncio
import logging

from app.core.database import async_session_factory
from app.services.published_content import PublishedContentService

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 30.0


class PublishScheduler:
    """Lightweight in-process poller that promotes due scheduled publishes.

    This is intentionally narrow and single-purpose: it repeatedly calls
    `PublishedContentService.promote_due` on its own DB session. It is not a
    general job/task queue, has no retry policy, and does not persist any
    state of its own — `PublishedContent.status`/`scheduled_at` are the only
    source of truth. Real platform publish calls stay behind the manual/no-op
    `ManualPlatformAdapter` until a real adapter is implemented.
    """

    def __init__(self, poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS):
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def run_once(self) -> int:
        async with async_session_factory() as session:
            service = PublishedContentService(session)
            promoted = await service.promote_due()
            await session.commit()
            return len(promoted)

    async def _run(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Publish scheduler tick failed")
            await asyncio.sleep(self._poll_interval_seconds)
