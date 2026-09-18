"""YouTube (Google OAuth 2.0 + YouTube Data API v3).

Destination model
-----------------

One Google account can manage several YouTube channels -- its own, plus any
number of **Brand Account** channels. `channels.list(mine=true)` returns
every one of them, and picking the wrong one silently publishes to the
wrong channel, which is precisely the failure this day exists to prevent.
So the destination list is always the full `channels.list` result and the
first entry is never assumed to be the intended one.

Token lifecycle (differs from Facebook/Instagram -- see `facebook.py`)
---------------------------------------------------------------------

Google returns a short-lived access token (~1h) plus, *only* when the
authorization request carries `access_type=offline` and `prompt=consent`, a
long-lived refresh token. Both are requested here, because without the
refresh token the connection would silently die an hour after the user
connects and there would be nothing for the proactive-refresh job to do.

Google issues **no per-channel credential**: the account token is what
authorizes uploads, and the channel choice is carried by
`external_account_id` alone. `Destination.access_token` is therefore left
`None` here, and the service records that the stored token is account-level
for this platform. That is a real platform difference, not a shortcut.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.platform_connections.models import SocialPlatform
from app.platform_connections.oauth.base import (
    Destination,
    OAuthConfigurationError,
    UserCredentials,
    raise_for_platform_error,
    require_access_token,
)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"

# Minimum viable scope set: `youtube.readonly` is what `channels.list`
# needs to enumerate destinations at all, and `youtube.upload` is the
# narrowest publish scope (it grants uploading, not full account
# management the way the broad `youtube` scope would). No analytics,
# no account-management, no profile scopes.
SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
)


class YouTubeOAuthProvider:
    platform = SocialPlatform.YOUTUBE
    scopes = SCOPES
    # Google issues no per-channel credential -- the account token is what
    # authorizes uploads, and the channel choice rides on
    # `external_account_id` alone.
    issues_destination_token = False

    def _credentials(self) -> tuple[str, str]:
        client_id = settings.youtube_oauth_client_id
        client_secret = settings.youtube_oauth_client_secret
        if not client_id or not client_secret:
            raise OAuthConfigurationError("YouTube OAuth client credentials are not configured")
        return client_id, client_secret

    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        client_id, _ = self._credentials()
        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                # Both are required for Google to return a refresh token.
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTHORIZATION_ENDPOINT}?{query}"

    async def exchange_code(
        self, *, code: str, redirect_uri: str, client: httpx.AsyncClient
    ) -> UserCredentials:
        client_id, client_secret = self._credentials()
        response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        raise_for_platform_error(response, "YouTube code exchange")
        return _credentials_from_token_response(response.json())

    async def list_destinations(
        self, *, credentials: UserCredentials, client: httpx.AsyncClient
    ) -> list[Destination]:
        """Every channel this Google account manages, Brand Accounts included."""
        response = await client.get(
            CHANNELS_ENDPOINT,
            params={"part": "id,snippet", "mine": "true", "maxResults": 50},
            headers={"Authorization": f"Bearer {credentials.access_token}"},
        )
        raise_for_platform_error(response, "YouTube channel listing")

        destinations: list[Destination] = []
        for item in response.json().get("items", []):
            channel_id = item.get("id")
            if not channel_id:
                continue
            snippet = item.get("snippet") or {}
            destinations.append(
                Destination(
                    external_account_id=str(channel_id),
                    external_account_name=snippet.get("title"),
                    # Google issues no per-channel token; the service falls
                    # back to the account-level token for this platform.
                    access_token=None,
                    metadata={"custom_url": snippet.get("customUrl")},
                )
            )
        return destinations

    async def refresh(self, *, refresh_token: str, client: httpx.AsyncClient) -> UserCredentials:
        client_id, client_secret = self._credentials()
        response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
        )
        raise_for_platform_error(response, "YouTube token refresh")
        refreshed = _credentials_from_token_response(response.json())
        # A refresh response usually omits `refresh_token`; the existing one
        # stays valid, so carry it forward rather than nulling the column.
        if refreshed.refresh_token is None:
            return UserCredentials(
                access_token=refreshed.access_token,
                refresh_token=refresh_token,
                expires_at=refreshed.expires_at,
                scopes=refreshed.scopes,
            )
        return refreshed

    async def revoke(self, *, access_token: str, client: httpx.AsyncClient) -> bool:
        """Google supports real revocation; failure is reported, not raised,
        so disconnect still deletes the local credential either way.
        """
        response = await client.post(REVOKE_ENDPOINT, data={"token": access_token})
        return response.is_success


def _credentials_from_token_response(payload: dict) -> UserCredentials:
    expires_in = payload.get("expires_in")
    expires_at = (
        datetime.now(UTC) + timedelta(seconds=int(expires_in)) if expires_in is not None else None
    )
    raw_scope = payload.get("scope") or ""
    return UserCredentials(
        access_token=require_access_token(payload, "Google token response"),
        refresh_token=payload.get("refresh_token"),
        expires_at=expires_at,
        scopes=raw_scope.split() if raw_scope else list(SCOPES),
    )
