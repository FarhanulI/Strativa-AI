import fakeredis.aioredis as fakeredis

from app.infrastructure.cache.service import CacheService


async def _fake_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


async def test_get_or_compute_calls_compute_fn_once_then_caches() -> None:
    redis = await _fake_client()
    cache = CacheService(redis, default_ttl_seconds=60)
    calls = 0

    async def compute() -> dict:
        nonlocal calls
        calls += 1
        return {"value": 42}

    first = await cache.get_or_compute("profile:1:brand", compute)
    second = await cache.get_or_compute("profile:1:brand", compute)

    assert first == {"value": 42}
    assert second == {"value": 42}
    assert calls == 1


async def test_invalidate_forces_recompute() -> None:
    redis = await _fake_client()
    cache = CacheService(redis, default_ttl_seconds=60)
    calls = 0

    async def compute() -> int:
        nonlocal calls
        calls += 1
        return calls

    await cache.get_or_compute("profile:1:brand", compute)
    await cache.invalidate("profile:1:brand")
    second = await cache.get_or_compute("profile:1:brand", compute)

    assert calls == 2
    assert second == 2


async def test_invalidate_prefix_clears_only_matching_namespace() -> None:
    redis = await _fake_client()
    cache = CacheService(redis, default_ttl_seconds=60)

    async def compute() -> str:
        return "v"

    await cache.get_or_compute("profile:1:brand", compute)
    await cache.get_or_compute("profile:1:audience", compute)
    await cache.get_or_compute("profile:2:brand", compute)

    deleted = await cache.invalidate_prefix("profile:1:")

    assert deleted == 2
    assert await redis.get("profile:1:brand") is None
    assert await redis.get("profile:1:audience") is None
    assert await redis.get("profile:2:brand") is not None
