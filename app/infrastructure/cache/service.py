import json
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

_SCAN_COUNT = 500


class CacheService:
    """Thin async cache wrapping Redis.

    Key convention: namespaced, colon-separated keys scoped to the entity
    they describe, e.g. ``profile:{profile_id}:brand`` or
    ``profile:{profile_id}:opportunities:list``. `invalidate_prefix` clears
    every key sharing a namespace (e.g. ``profile:{profile_id}:``) so a
    single profile's cached reads can be dropped together without touching
    other tenants.

    Nothing in the product currently calls this service — it exists as
    reusable infrastructure for later days to wire into specific reads.
    """

    def __init__(self, redis: Redis, default_ttl_seconds: int | None = None):
        self._redis = redis
        self._default_ttl_seconds = default_ttl_seconds or settings.cache_default_ttl_seconds

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[Any]],
        ttl: int | None = None,
    ) -> Any:
        cached = await self._redis.get(key)
        if cached is not None:
            return json.loads(cached)

        value = await compute_fn()
        await self._redis.set(key, json.dumps(value), ex=ttl or self._default_ttl_seconds)
        return value

    async def invalidate(self, key: str) -> None:
        await self._redis.delete(key)

    async def invalidate_prefix(self, prefix: str) -> int:
        """Delete every key starting with `prefix` using non-blocking SCAN
        (never KEYS, which blocks the Redis event loop on a large keyspace).
        """
        deleted = 0
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=_SCAN_COUNT)
            if keys:
                deleted += await self._redis.delete(*keys)
            if cursor == 0:
                break
        return deleted
