"""Real `PlatformAdapter` implementations for YouTube, Facebook, and
Instagram -- **connection/authorization surface only** (Day 23).

Day 9 defined `SocialPlatformAdapter` as a contract with `fetch_posts` /
`fetch_post` / `fetch_metrics` / `publish`, and listed `connect()`,
`refresh_token()`, `disconnect()`, `fetch_profile()` as the future
connection/authorization methods. This module implements that second group
for real, against a stored `PlatformConnection`, and leaves the first group
typed but unimplemented.

`publish` is deliberately a typed stub that raises. Wiring connections into
the publish flow is Day 24; a stub that silently returned a plausible
success would be considerably worse than one that refuses, because Day 24
would then have nothing to notice.

These adapters are the uniform shape Day 24 consumes: it gets a
`PlatformConnection` and asks the adapter for a usable access token,
without knowing that Facebook's is a Page token and YouTube's is an
account token.
"""

from typing import Any, Protocol

import httpx

from app.integrations.social import SocialPlatformAdapter
from app.platform_connections.crypto import decrypt_token
from app.platform_connections.models import ConnectionStatus, PlatformConnection, SocialPlatform
from app.platform_connections.oauth import get_provider
from app.platform_connections.oauth.base import Destination, UserCredentials


class PlatformConnectionAdapter(SocialPlatformAdapter, Protocol):
    """The Day 9 contract's connection/authorization surface, made concrete.

    Literally extends `app.integrations.social.SocialPlatformAdapter`: the
    content/metrics half of that Protocol (`fetch_posts`/`fetch_post`/
    `fetch_metrics`/`publish`) is inherited exactly as Day 9 defined it,
    and this adds the authorization half Day 9 anticipated
    (`connect`/`refresh_token`/`disconnect`/`fetch_profile`).
    """

    platform: SocialPlatform

    def authorization_url(self, *, redirect_uri: str, state: str) -> str: ...

    async def exchange_code(
        self, *, code: str, redirect_uri: str, client: httpx.AsyncClient
    ) -> UserCredentials: ...

    async def list_destinations(
        self, *, credentials: UserCredentials, client: httpx.AsyncClient
    ) -> list[Destination]: ...

    async def refresh_token(
        self, connection: PlatformConnection, *, client: httpx.AsyncClient
    ) -> UserCredentials: ...

    async def disconnect(
        self, connection: PlatformConnection, *, client: httpx.AsyncClient
    ) -> bool: ...

    def access_token(self, connection: PlatformConnection) -> str: ...

    async def publish(self, *, draft: dict[str, Any], platform: str) -> dict[str, Any]: ...


class _BaseConnectionAdapter:
    """Shared implementation: every method delegates to the platform's
    OAuth provider, so adapter and OAuth submodule can never drift apart
    on endpoints, scopes, or token semantics.
    """

    platform: SocialPlatform

    @property
    def _provider(self):
        return get_provider(self.platform)

    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        return self._provider.authorization_url(redirect_uri=redirect_uri, state=state)

    async def exchange_code(
        self, *, code: str, redirect_uri: str, client: httpx.AsyncClient
    ) -> UserCredentials:
        return await self._provider.exchange_code(
            code=code, redirect_uri=redirect_uri, client=client
        )

    async def list_destinations(
        self, *, credentials: UserCredentials, client: httpx.AsyncClient
    ) -> list[Destination]:
        return await self._provider.list_destinations(credentials=credentials, client=client)

    async def refresh_token(
        self, connection: PlatformConnection, *, client: httpx.AsyncClient
    ) -> UserCredentials:
        if connection.refresh_token_encrypted is None:
            raise NotImplementedError(
                f"{self.platform} connections have no refresh token to refresh with"
            )
        return await self._provider.refresh(
            refresh_token=decrypt_token(connection.refresh_token_encrypted), client=client
        )

    async def disconnect(
        self, connection: PlatformConnection, *, client: httpx.AsyncClient
    ) -> bool:
        return await self._provider.revoke(
            access_token=self.access_token(connection), client=client
        )

    def access_token(self, connection: PlatformConnection) -> str:
        """Decrypt the stored credential for use against the platform API.

        The single place a stored token is turned back into plaintext for
        an outbound call. Refuses a connection that isn't currently
        `connected`, so an expired/revoked credential fails loudly here
        rather than as an opaque 401 from the platform at publish time.
        """
        if connection.status is not ConnectionStatus.CONNECTED:
            raise ValueError(f"Connection {connection.id} is {connection.status}, not connected")
        return decrypt_token(connection.access_token_encrypted)

    # --- Day 24 surface: typed, not implemented ---------------------------

    async def publish(self, *, draft: dict[str, Any], platform: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Publishing through platform connections is Day 24; Day 23 implements the "
            "connection/authorization surface only"
        )

    async def fetch_posts(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def fetch_post(self, external_post_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_metrics(self, external_post_id: str) -> dict[str, Any]:
        raise NotImplementedError


class YouTubeAdapter(_BaseConnectionAdapter):
    """YouTube Data API v3. `external_account_id` is a Channel ID; the
    stored token is account-level because Google issues no per-channel
    credential (see `oauth/youtube.py`).
    """

    platform = SocialPlatform.YOUTUBE


class FacebookAdapter(_BaseConnectionAdapter):
    """Graph API, Page-level publishing. `external_account_id` is a Page ID
    and the stored token is that Page's own access token.
    """

    platform = SocialPlatform.FACEBOOK


class InstagramAdapter(_BaseConnectionAdapter):
    """Graph API via the linked Facebook Business account.
    `external_account_id` is an Instagram Business Account ID; the stored
    token is the linked Page's token (see `oauth/instagram.py`).
    """

    platform = SocialPlatform.INSTAGRAM


_ADAPTERS: dict[SocialPlatform, PlatformConnectionAdapter] = {
    SocialPlatform.YOUTUBE: YouTubeAdapter(),
    SocialPlatform.FACEBOOK: FacebookAdapter(),
    SocialPlatform.INSTAGRAM: InstagramAdapter(),
}


def get_adapter(platform: SocialPlatform) -> PlatformConnectionAdapter:
    """The uniform lookup Day 24 will consume connections through."""
    adapter = _ADAPTERS.get(platform)
    if adapter is None:  # pragma: no cover - SocialPlatform is exhaustive
        raise ValueError(f"No platform adapter implemented for '{platform}'")
    return adapter
