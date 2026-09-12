from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from redis.exceptions import LockError

from app.core.config import settings


class LockAcquisitionError(RuntimeError):
    """Raised when a distributed lock could not be acquired before blocking_timeout."""


class DistributedLock:
    """Redis-backed distributed lock (SET NX PX with a token-checked, safe
    release) for coordinating work across multiple app/worker instances —
    e.g. the publish scheduler ensuring only one instance promotes a given
    batch of due rows at a time.

    Usage:
        async with DistributedLock(redis, "publish-scheduler:tick"):
            ...
    """

    def __init__(
        self,
        redis: Redis,
        name: str,
        timeout_seconds: float | None = None,
        blocking_timeout_seconds: float = 0,
    ):
        """`blocking_timeout_seconds` defaults to 0 — a single, immediate,
        non-blocking acquisition attempt (the standard "try-lock" semantics
        wanted for coordinating pollers/schedulers). Pass a positive value
        to wait up to that many seconds for the lock to free up instead.
        """
        self._redis = redis
        self._name = f"lock:{name}"
        self._timeout_seconds = timeout_seconds or settings.lock_default_timeout_seconds
        self._blocking_timeout_seconds = blocking_timeout_seconds
        self._lock = redis.lock(
            self._name,
            timeout=self._timeout_seconds,
            blocking=blocking_timeout_seconds > 0,
            blocking_timeout=blocking_timeout_seconds or None,
        )

    async def __aenter__(self) -> "DistributedLock":
        acquired = await self._lock.acquire()
        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock '{self._name}'")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self._lock.release()
        except LockError:
            # Lock already expired/released — nothing left to clean up.
            pass


@asynccontextmanager
async def try_lock(
    redis: Redis, name: str, timeout_seconds: float | None = None
) -> AsyncIterator[bool]:
    """Non-blocking variant: yields True if the lock was acquired, False
    otherwise, and releases automatically on exit if it was acquired.
    """
    lock = DistributedLock(redis, name, timeout_seconds=timeout_seconds)
    try:
        await lock.__aenter__()
    except LockAcquisitionError:
        yield False
        return
    try:
        yield True
    finally:
        await lock.__aexit__(None, None, None)
