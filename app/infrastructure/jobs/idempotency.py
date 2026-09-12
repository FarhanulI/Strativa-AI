from redis.asyncio import Redis

from app.core.config import settings


async def claim_idempotency_key(
    redis: Redis, scope: str, idempotency_key: str, ttl_seconds: int | None = None
) -> bool:
    """Redis-backed short-TTL dedup for job-submission endpoints.

    `scope` namespaces the key by endpoint/operation (e.g. "briefs.generate")
    so the same client-supplied Idempotency-Key can't collide across
    unrelated operations. Returns True the first time a given
    (scope, idempotency_key) pair is seen within the TTL window — the caller
    should proceed and submit the job. Returns False on a retry within that
    window — the caller should skip submission (the earlier request is
    still being processed or already completed).

    Uses `SET key value NX EX ttl`, which is atomic: concurrent retries can
    never both win the claim.
    """
    redis_key = f"idempotency:{scope}:{idempotency_key}"
    ttl = ttl_seconds or settings.idempotency_key_ttl_seconds
    claimed = await redis.set(redis_key, "1", nx=True, ex=ttl)
    return bool(claimed)
