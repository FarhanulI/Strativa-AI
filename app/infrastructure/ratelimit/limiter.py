import time
import uuid

from redis.asyncio import Redis

from app.infrastructure.ratelimit.policy import RateLimitRule


async def check_sliding_window(redis: Redis, key: str, rule: RateLimitRule) -> tuple[bool, int]:
    """Redis sorted-set sliding-window counter.

    Each request adds a uniquely-named member scored by its timestamp;
    members older than the window are trimmed before counting, so the count
    always reflects requests in the trailing `window_seconds`, not a fixed
    calendar bucket.

    Returns (allowed, remaining). A rejected request is NOT recorded, so a
    client that backs off does not keep consuming budget.
    """
    now = time.time()
    window_start = now - rule.window_seconds
    redis_key = f"ratelimit:{key}"

    await redis.zremrangebyscore(redis_key, 0, window_start)
    current = await redis.zcard(redis_key)

    if current >= rule.max_requests:
        return False, 0

    member = f"{now}:{uuid.uuid4().hex}"
    await redis.zadd(redis_key, {member: now})
    await redis.expire(redis_key, rule.window_seconds)
    return True, rule.max_requests - (current + 1)
