"""Per-platform OAuth submodules (Day 23).

Each provider handles authorization-URL building, token exchange, AND
destination listing for one platform. `get_provider` is the only lookup --
nothing else in the codebase branches on platform name.
"""

from app.platform_connections.models import SocialPlatform
from app.platform_connections.oauth.base import (
    Destination,
    OAuthConfigurationError,
    OAuthExchangeError,
    OAuthProvider,
    UserCredentials,
    build_http_client,
)
from app.platform_connections.oauth.facebook import FacebookOAuthProvider
from app.platform_connections.oauth.instagram import InstagramOAuthProvider
from app.platform_connections.oauth.youtube import YouTubeOAuthProvider

_PROVIDERS: dict[SocialPlatform, OAuthProvider] = {
    SocialPlatform.YOUTUBE: YouTubeOAuthProvider(),
    SocialPlatform.FACEBOOK: FacebookOAuthProvider(),
    SocialPlatform.INSTAGRAM: InstagramOAuthProvider(),
}


def get_provider(platform: SocialPlatform) -> OAuthProvider:
    provider = _PROVIDERS.get(platform)
    if provider is None:  # pragma: no cover - SocialPlatform is exhaustive
        raise OAuthConfigurationError(f"No OAuth provider implemented for '{platform}'")
    return provider


__all__ = [
    "Destination",
    "FacebookOAuthProvider",
    "InstagramOAuthProvider",
    "OAuthConfigurationError",
    "OAuthExchangeError",
    "OAuthProvider",
    "UserCredentials",
    "YouTubeOAuthProvider",
    "build_http_client",
    "get_provider",
]
