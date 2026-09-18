"""Facebook Pages (Graph API).

Destination model
-----------------

One Facebook login may administer many Pages. `GET /me/accounts` returns
every Page the authenticated user administers **and each Page's own Page
Access Token in the same response**, which is what makes per-destination
scoping possible without a second round trip per Page.

Publishing happens as the Page, using the Page token -- never as the user
with the user token. So the stored credential is always the Page-scoped one
and `external_account_id` is always the Page ID.

Token lifecycle (differs from YouTube -- see `youtube.py`)
----------------------------------------------------------

The code exchange yields a *short-lived* user token. It is immediately
exchanged for a *long-lived* user token (~60 days) via
`grant_type=fb_exchange_token`, because Page tokens derived from a
short-lived user token inherit its short life, whereas Page tokens derived
from a long-lived user token **do not expire**.

Consequently a Facebook connection legitimately stores no refresh token and
(usually) no expiry: there is no refresh-token grant in this flow at all.
That is why `refresh_token_encrypted` and `token_expires_at` are nullable
on the model rather than being an unfinished detail.
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

# Minimum viable scopes: list the Pages the user administers, read the Page
# context needed to resolve a Page token, and publish as the Page. No ads,
# no insights, no user-profile, no messaging scopes.
SCOPES: tuple[str, ...] = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
)


def graph_base() -> str:
    return f"https://graph.facebook.com/{settings.facebook_graph_api_version}"


def authorization_endpoint() -> str:
    return f"https://www.facebook.com/{settings.facebook_graph_api_version}/dialog/oauth"


class FacebookOAuthProvider:
    platform = SocialPlatform.FACEBOOK
    scopes = SCOPES
    # Every Page returned by `/me/accounts` carries its own Page token.
    issues_destination_token = True

    def _credentials(self) -> tuple[str, str]:
        client_id = settings.facebook_oauth_client_id
        client_secret = settings.facebook_oauth_client_secret
        if not client_id or not client_secret:
            raise OAuthConfigurationError("Facebook OAuth client credentials are not configured")
        return client_id, client_secret

    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        client_id, _ = self._credentials()
        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": ",".join(self.scopes),
                "state": state,
            }
        )
        return f"{authorization_endpoint()}?{query}"

    async def exchange_code(
        self, *, code: str, redirect_uri: str, client: httpx.AsyncClient
    ) -> UserCredentials:
        """Short-lived user token, then immediately upgraded to long-lived."""
        client_id, client_secret = self._credentials()
        response = await client.get(
            f"{graph_base()}/oauth/access_token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        raise_for_platform_error(response, "Facebook code exchange")
        short_lived = require_access_token(response.json(), "Facebook code exchange")

        return await self._exchange_for_long_lived(short_lived, client)

    async def _exchange_for_long_lived(
        self, short_lived_token: str, client: httpx.AsyncClient
    ) -> UserCredentials:
        client_id, client_secret = self._credentials()
        response = await client.get(
            f"{graph_base()}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "fb_exchange_token": short_lived_token,
            },
        )
        raise_for_platform_error(response, "Facebook long-lived token exchange")
        payload = response.json()

        expires_in = payload.get("expires_in")
        return UserCredentials(
            access_token=require_access_token(payload, "Facebook long-lived token exchange"),
            # No refresh-token grant exists in this flow at all.
            refresh_token=None,
            expires_at=(
                datetime.now(UTC) + timedelta(seconds=int(expires_in))
                if expires_in is not None
                else None
            ),
            scopes=list(self.scopes),
        )

    async def list_destinations(
        self, *, credentials: UserCredentials, client: httpx.AsyncClient
    ) -> list[Destination]:
        """Every Page the user administers, each with its own Page token."""
        pages = await fetch_administered_pages(access_token=credentials.access_token, client=client)
        return [
            Destination(
                external_account_id=page["id"],
                external_account_name=page.get("name"),
                # The Page-scoped token -- this, not the user token, is what
                # gets stored once this destination is selected.
                access_token=page.get("access_token"),
                metadata={"category": page.get("category")},
            )
            for page in pages
            # A Page with no `access_token` cannot be published to as that
            # Page, so it must not be offered as a destination -- it would
            # look connectable and then either fail at publish time or, worse,
            # tempt a fallback to the user token.
            if page.get("id") and page.get("access_token")
        ]

    async def refresh(self, *, refresh_token: str, client: httpx.AsyncClient) -> UserCredentials:
        """Facebook has no refresh-token grant for Page tokens.

        A long-lived-user-derived Page token does not expire, so there is
        nothing to refresh; a connection that genuinely does lapse has to be
        reconnected through the full flow. Raising (rather than silently
        returning the same token) keeps the refresh job honest -- it marks
        the connection `expired` and surfaces it, instead of pretending a
        refresh succeeded.
        """
        raise NotImplementedError(
            "Facebook Page tokens have no refresh grant; reconnect is required"
        )

    async def revoke(self, *, access_token: str, client: httpx.AsyncClient) -> bool:
        """Best-effort de-authorization.

        Full app de-authorization needs the *user* token, which this day
        deliberately never persists (only the Page token is stored). The
        Page token can still revoke the Page's own grant via
        `DELETE /me/permissions`, so that is attempted; whatever the
        platform answers, the caller deletes the local credential.
        """
        response = await client.delete(
            f"{graph_base()}/me/permissions",
            params={"access_token": access_token},
        )
        return response.is_success


async def fetch_administered_pages(*, access_token: str, client: httpx.AsyncClient) -> list[dict]:
    """`GET /me/accounts` -- shared by the Facebook and Instagram providers.

    Instagram reuses this because an Instagram Business Account is always
    reached *through* the Page it is linked to (see `instagram.py`).
    """
    response = await client.get(
        f"{graph_base()}/me/accounts",
        params={
            "fields": "id,name,category,access_token,instagram_business_account{id,username,name}",
            "limit": 100,
            "access_token": access_token,
        },
    )
    raise_for_platform_error(response, "Facebook page listing")
    return response.json().get("data", [])
