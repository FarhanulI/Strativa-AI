"""Instagram (Graph API, via the linked Facebook Business account).

Destination model
-----------------

Instagram publishing does not run against an Instagram login. It runs
against an **Instagram Business Account**, which is reachable only through
the Facebook Page it is linked to. So the flow is Facebook's flow, with one
extra hop: enumerate the Pages the user administers, and for each Page read
its `instagram_business_account` field.

Two consequences this module makes explicit:

* A Page with no linked Instagram Business Account is **not** a valid
  Instagram destination and is filtered out entirely -- it would look
  connectable and then fail at publish time.
* `external_account_id` is the **Instagram Business Account ID**, not the
  Page ID and not the user ID, because that is the id every Instagram
  publish call is addressed to. The originating Page ID is kept in
  `metadata` for traceability, since the stored token is that Page's token.

The credential stored is the linked **Page's** access token -- Instagram
Graph publishing authorizes with the Page token, and there is no separate
Instagram-scoped credential to obtain.
"""

from urllib.parse import urlencode

import httpx

from app.platform_connections.models import SocialPlatform
from app.platform_connections.oauth.base import Destination, UserCredentials
from app.platform_connections.oauth.facebook import (
    FacebookOAuthProvider,
    authorization_endpoint,
    fetch_administered_pages,
)

# Minimum viable scopes: Facebook's Page-listing scope (the only way to
# reach a linked Instagram account), plus Instagram read and publish. No
# ads, no insights, no comment-moderation, no messaging scopes.
SCOPES: tuple[str, ...] = (
    "pages_show_list",
    "pages_read_engagement",
    "instagram_basic",
    "instagram_content_publish",
)


class InstagramOAuthProvider(FacebookOAuthProvider):
    """Reuses Facebook's token exchange/refresh/revoke wholesale.

    Subclassing rather than duplicating is correct here: the OAuth grant
    genuinely *is* Facebook's (same app, same endpoints, same long-lived
    user-token upgrade, same absence of a refresh grant). Only the scope
    set and what counts as a destination differ, and those are exactly the
    two things overridden.
    """

    platform = SocialPlatform.INSTAGRAM
    scopes = SCOPES
    # Publishing authorizes with the linked Page's token.
    issues_destination_token = True

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

    async def list_destinations(
        self, *, credentials: UserCredentials, client: httpx.AsyncClient
    ) -> list[Destination]:
        pages = await fetch_administered_pages(access_token=credentials.access_token, client=client)

        destinations: list[Destination] = []
        for page in pages:
            linked = page.get("instagram_business_account")
            if not linked or not linked.get("id"):
                # No linked Business Account -- publishing here is
                # impossible, so it must not appear as a choice.
                continue
            if not page.get("access_token"):
                # Same reasoning: without the linked Page's token there is
                # no credential to publish with.
                continue
            destinations.append(
                Destination(
                    external_account_id=str(linked["id"]),
                    external_account_name=linked.get("username") or linked.get("name"),
                    # The linked Page's token is the publishing credential.
                    access_token=page.get("access_token"),
                    metadata={
                        "facebook_page_id": page.get("id"),
                        "facebook_page_name": page.get("name"),
                    },
                )
            )
        return destinations
