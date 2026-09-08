from datetime import datetime
from typing import Any, Protocol


class SocialPlatformAdapter(Protocol):
    async def fetch_posts(self) -> list[dict[str, Any]]: ...
    async def fetch_post(self, external_post_id: str) -> dict[str, Any]: ...
    async def fetch_metrics(self, external_post_id: str) -> dict[str, Any]: ...


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
