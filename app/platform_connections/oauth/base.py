"""Shared contract for the per-platform OAuth providers.

Each provider owns three things and nothing else: building an
authorization URL, exchanging a code for a **user-level** token, and
listing the destinations that user-level token can publish to. Persistence,
authorization, and encryption all live above this layer in
`app/platform_connections/service.py` -- a provider never touches the
database, never sees a `ContentProfile`, and never decides whether a caller
is allowed to do anything.

The `Destination` split is the point of this day: `token_exchange` returns
credentials for an *account*, `list_destinations` returns the several
*places* that account can actually publish to, and only the selection step
turns one of those into a stored connection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import httpx

from app.core.config import settings


class OAuthConfigurationError(RuntimeError):
    """Raised when a platform's OAuth client credentials aren't configured."""


class MissingDestinationTokenError(RuntimeError):
    """Raised when a platform that should issue a destination-scoped token
    did not return one for the selected destination.

    Explicitly an error rather than a fallback: silently storing the
    user-level token instead would hand us a credential covering every
    destination the person administers, exactly the blast radius this day
    exists to avoid.
    """


class OAuthExchangeError(RuntimeError):
    """Raised when a platform rejects a code exchange, refresh, or API call.

    Carries only the platform's status/summary -- never the code, token, or
    client secret involved, because this message reaches logs and (as a 502
    detail) HTTP responses.
    """


@dataclass(frozen=True)
class UserCredentials:
    """The *account-level* credentials from a code exchange.

    Never persisted to Postgres. For Facebook/Instagram this is the user
    token used only to enumerate Pages and read their Page tokens; for
    YouTube it is the Google account token, which is also what ends up
    stored, because Google issues no per-channel credential (see
    `youtube.py`).
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Destination:
    """One publishable place the authenticated account administers.

    `access_token` is the *destination-scoped* credential where the platform
    issues one (a Facebook Page token); `None` where it does not (YouTube),
    in which case the service falls back to the user-level token and records
    why in the connection's metadata.
    """

    external_account_id: str
    external_account_name: str | None = None
    access_token: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OAuthProvider(Protocol):
    """What every platform's OAuth submodule implements."""

    platform: str
    scopes: tuple[str, ...]

    # Whether this platform issues a credential scoped to the individual
    # destination (a Facebook Page token) as opposed to only an
    # account-level one (Google/YouTube). Declared per platform rather than
    # inferred from whether a token happened to come back in the response:
    # `/me/accounts` omits `access_token` for a Page whenever the caller's
    # role or granted scopes don't yield one, and inferring from that would
    # silently fall back to persisting the long-lived USER token while
    # labelling it account-scoped.
    issues_destination_token: bool

    def authorization_url(self, *, redirect_uri: str, state: str) -> str: ...

    async def exchange_code(
        self, *, code: str, redirect_uri: str, client: httpx.AsyncClient
    ) -> UserCredentials: ...

    async def list_destinations(
        self, *, credentials: UserCredentials, client: httpx.AsyncClient
    ) -> list[Destination]: ...

    async def refresh(
        self, *, refresh_token: str, client: httpx.AsyncClient
    ) -> UserCredentials: ...

    async def revoke(self, *, access_token: str, client: httpx.AsyncClient) -> bool: ...


def build_http_client() -> httpx.AsyncClient:
    """The one place outbound platform HTTP is constructed.

    Every provider takes its `httpx.AsyncClient` as an argument rather than
    creating one, so tests inject a `MockTransport` and no test ever reaches
    the network.
    """
    return httpx.AsyncClient(timeout=settings.platform_http_timeout_seconds)


def require_access_token(payload: dict, action: str) -> str:
    """Read `access_token` from a 2xx body without assuming it is there.

    A platform can answer 200 with an unexpected shape (or a proxy can
    return an HTML error page). A bare `KeyError` would escape the router's
    error mapping as a 500; this keeps every platform failure normalized to
    the deliberate 502.
    """
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token or not isinstance(token, str):
        raise OAuthExchangeError(f"Platform response for {action} contained no access token")
    return token


def raise_for_platform_error(response: httpx.Response, action: str) -> None:
    """Normalize a platform HTTP failure without echoing the request body.

    The request body is exactly where the code/secret/token live, so it is
    never included -- only the platform's own status and (truncated)
    response text.
    """
    if response.is_success:
        return
    raise OAuthExchangeError(
        f"Platform rejected {action} (HTTP {response.status_code}): {response.text[:300]}"
    )
