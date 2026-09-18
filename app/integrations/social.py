from datetime import datetime
from typing import Any, Protocol


class SocialPlatformAdapter(Protocol):
    """Day 9's content/metrics contract, unchanged.

    Day 23 implements the *connection/authorization* half Day 9 anticipated
    (`connect()`, `refresh_token()`, `disconnect()`, `fetch_profile()`) as
    `app.platform_connections.adapters.PlatformConnectionAdapter`, with real
    YouTube/Facebook/Instagram implementations. That Protocol extends this
    one rather than replacing it, so this contract stays the single
    definition of the content/metrics surface.
    """

    async def fetch_posts(self) -> list[dict[str, Any]]: ...
    async def fetch_post(self, external_post_id: str) -> dict[str, Any]: ...
    async def fetch_metrics(self, external_post_id: str) -> dict[str, Any]: ...
    async def publish(self, *, draft: dict[str, Any], platform: str) -> dict[str, Any]: ...


class ManualPlatformAdapter:
    """No-op adapter used for manual publish confirmation.

    Real platform publishing (OAuth, API calls) stays a future implementation
    behind this same `SocialPlatformAdapter` contract.
    """

    async def fetch_posts(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def fetch_post(self, external_post_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_metrics(self, external_post_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def publish(self, *, draft: dict[str, Any], platform: str) -> dict[str, Any]:
        return {"status": "published", "external_url": None}


def normalize_performance(
    *,
    external_post_id: str | None,
    platform: str,
    published_at: datetime | None,
    content_type: str | None,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "external_post_id": external_post_id,
        "platform": platform,
        "published_at": published_at,
        "content_type": content_type,
        **metrics,
    }
