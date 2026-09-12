import asyncio

import fakeredis.aioredis as fakeredis
from httpx import ASGITransport, AsyncClient

from app.infrastructure.ratelimit.limiter import check_sliding_window
from app.infrastructure.ratelimit.policy import RateLimitRule
from app.main import app


async def test_sliding_window_blocks_after_threshold_and_resets_after_window() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)
    rule = RateLimitRule(max_requests=3, window_seconds=1)

    for _ in range(3):
        allowed, _ = await check_sliding_window(redis, "test:key", rule)
        assert allowed is True

    blocked, remaining = await check_sliding_window(redis, "test:key", rule)
    assert blocked is False
    assert remaining == 0

    await asyncio.sleep(1.1)

    allowed_after_reset, _ = await check_sliding_window(redis, "test:key", rule)
    assert allowed_after_reset is True


async def test_middleware_returns_429_once_limit_exceeded(monkeypatch) -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.infrastructure.ratelimit.middleware.get_redis", lambda: fake)
    monkeypatch.setattr("app.infrastructure.ratelimit.middleware.settings.rate_limit_enabled", True)
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.rate_limit_crud_requests_per_window", 2
    )
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.rate_limit_window_seconds", 60
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/")
        second = await client.get("/")
        third = await client.get("/")

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert "Retry-After" in third.headers
