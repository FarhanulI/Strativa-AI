from arq.connections import ArqRedis

from app.core.config import settings

_pool: ArqRedis | None = None


def get_arq_pool() -> ArqRedis:
    """Shared arq connection for the API process to enqueue jobs with.

    Mirrors `app.infrastructure.redis_client.get_redis`'s single-instance
    pattern; module-level rather than `lru_cache` only because tests need to
    monkeypatch the module attribute directly (the `arq` client, unlike
    `redis.asyncio.Redis`, has no cheap synchronous constructor to swap for
    a fake in the same call signature).
    """
    global _pool
    if _pool is None:
        _pool = ArqRedis.from_url(settings.redis_url)
    return _pool
