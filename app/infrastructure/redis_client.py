from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import settings


@lru_cache
def get_redis() -> Redis:
    """Shared async Redis client for the API process.

    A single connection pool is reused across requests. Domain services must
    never call this directly — only infrastructure services
    (CacheService, rate limit middleware, DistributedLock, idempotency
    helpers) hold a Redis client.
    """
    return Redis.from_url(settings.redis_url, decode_responses=True)
