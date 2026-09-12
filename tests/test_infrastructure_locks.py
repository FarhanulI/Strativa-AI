import fakeredis.aioredis as fakeredis
import pytest

from app.infrastructure.locks.service import DistributedLock, LockAcquisitionError, try_lock


async def test_lock_acquire_and_release_allows_sequential_reacquire() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)

    async with DistributedLock(redis, "publish-scheduler:tick", timeout_seconds=5):
        assert await redis.get("lock:publish-scheduler:tick") is not None

    async with DistributedLock(redis, "publish-scheduler:tick", timeout_seconds=5):
        assert await redis.get("lock:publish-scheduler:tick") is not None


async def test_second_holder_cannot_acquire_while_locked() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)

    async with DistributedLock(redis, "publish-scheduler:tick", timeout_seconds=5):
        with pytest.raises(LockAcquisitionError):
            async with DistributedLock(
                redis, "publish-scheduler:tick", timeout_seconds=5, blocking_timeout_seconds=0.1
            ):
                pass


async def test_try_lock_yields_false_when_contended() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)

    async with DistributedLock(redis, "publish-scheduler:tick", timeout_seconds=5):
        async with try_lock(redis, "publish-scheduler:tick") as acquired:
            assert acquired is False

    async with try_lock(redis, "publish-scheduler:tick") as acquired:
        assert acquired is True
