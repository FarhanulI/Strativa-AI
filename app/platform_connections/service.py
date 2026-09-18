"""Business rules for connecting a ContentProfile to a publishing
destination (Day 23).

The flow this service implements, and why it has three steps rather than
two:

    1. authorize          -> signed state + allowlisted authorization URL
    2. callback           -> USER-level token + the list of destinations
                             that account administers. Persists NOTHING.
    3. select_destination -> resolve the DESTINATION-scoped token for one
                             chosen Page/Channel and persist the connection

Step 2 stopping short of persistence is the whole point. One OAuth login
can administer several Pages/Channels, so "the account authorized us" does
not tell us where this profile publishes. Collapsing 2 and 3 -- persisting
the first destination the platform happens to return -- is the exact bug
this design prevents.

Authorization is layered, not single-point: the router runs Day 21's
`require_profile_access` on the path `profile_id`, and this service
additionally requires that the state-encoded (step 2) and pending-state
(step 3) `profile_id` match that verified profile. A forged or replayed
state therefore cannot attach a connection to a profile the caller does
not own -- it fails the membership check, the equality check, or both.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.content_profile import ContentProfile
from app.platform_connections import pending
from app.platform_connections.crypto import decrypt_token, encrypt_optional, encrypt_token
from app.platform_connections.models import ConnectionStatus, PlatformConnection, SocialPlatform
from app.platform_connections.oauth import get_provider
from app.platform_connections.oauth.base import (
    Destination,
    MissingDestinationTokenError,
    UserCredentials,
    build_http_client,
)
from app.platform_connections.repository import PlatformConnectionRepository
from app.platform_connections.state import InvalidOAuthStateError, issue_state, verify_state

logger = logging.getLogger(__name__)


class RedirectUriNotAllowedError(ValueError):
    """Raised when a requested redirect URI is not on the allowlist."""


class StateProfileMismatchError(ValueError):
    """Raised when a state/pending payload targets a different profile than
    the one the caller was authorized for.
    """


class DestinationNotAvailableError(ValueError):
    """Raised when a selected destination was not in the fetched list."""


class ConnectionNotFoundError(ValueError):
    """Raised when no connection exists for a profile/platform."""


class ConnectionConflictError(ValueError):
    """Raised when a concurrent selection already wrote this connection."""


class NoAvailableDestinationsError(ValueError):
    """Raised when an authorized account administers nothing publishable."""


def validate_redirect_uri(redirect_uri: str) -> str:
    """Exact-match allowlist check.

    Exact match, never a prefix or `startswith` test: a prefix check on
    `https://app.example.com/` happily accepts
    `https://app.example.com.evil.test/`, which is an open redirect and
    hands the authorization code to the attacker.
    """
    if redirect_uri not in settings.oauth_redirect_uri_allowlist:
        raise RedirectUriNotAllowedError("redirect_uri is not allowlisted")
    return redirect_uri


class PlatformConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PlatformConnectionRepository(session)

    # --- Step 1: authorize -------------------------------------------------

    def build_authorization(
        self, *, profile: ContentProfile, platform: SocialPlatform, redirect_uri: str
    ) -> tuple[str, str, list[str]]:
        validate_redirect_uri(redirect_uri)
        provider = get_provider(platform)

        state = issue_state(
            profile_id=profile.id,
            workspace_id=profile.workspace_id,
            platform=platform,
            redirect_uri=redirect_uri,
        )
        url = provider.authorization_url(redirect_uri=redirect_uri, state=state)
        return url, state, list(provider.scopes)

    # --- Step 2: callback (no persistence) ---------------------------------

    async def handle_callback(
        self,
        *,
        profile: ContentProfile,
        platform: SocialPlatform,
        state: str,
        code: str,
        redirect_uri: str,
        redis: Redis,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[str, int, list[Destination]]:
        """Exchange the code for a user-level token and list destinations.

        Returns `(selection_token, ttl_seconds, destinations)`. Persists no
        `PlatformConnection` -- the user-level token goes only into the
        encrypted, short-TTL Redis pending state.
        """
        payload = verify_state(state)

        # The state is signed, so it came from us -- but that says nothing
        # about who is replaying it. Bind it to the profile the caller was
        # actually authorized for, and to the platform/redirect_uri it was
        # issued for.
        if payload.get("profile_id") != str(profile.id):
            raise StateProfileMismatchError("OAuth state does not match the requested profile")
        if payload.get("platform") != str(platform):
            raise InvalidOAuthStateError("Invalid OAuth state")
        if payload.get("redirect_uri") != redirect_uri:
            raise InvalidOAuthStateError("Invalid OAuth state")
        validate_redirect_uri(redirect_uri)

        provider = get_provider(platform)
        owns_client = client is None
        client = client or build_http_client()
        try:
            credentials = await provider.exchange_code(
                code=code, redirect_uri=redirect_uri, client=client
            )
            destinations = await provider.list_destinations(credentials=credentials, client=client)
        finally:
            if owns_client:
                await client.aclose()

        if not destinations:
            # Nothing publishable: don't park a live user token in Redis for
            # ten minutes and hand the caller an empty picker with no
            # explanation. Common for Instagram, where a Page only counts if
            # it has a linked Business Account.
            raise NoAvailableDestinationsError(
                f"This account administers no {platform} destination this app can publish to"
            )

        selection_token, ttl = await pending.store(
            redis,
            profile_id=profile.id,
            workspace_id=profile.workspace_id,
            platform=platform,
            credentials=credentials,
            destinations=destinations,
        )
        logger.info(
            "platform_connection.callback_pending",
            extra={
                "profile_id": str(profile.id),
                "platform": str(platform),
                "destination_count": len(destinations),
            },
        )
        return selection_token, ttl, destinations

    # --- Step 3: destination selection (persists) --------------------------

    async def select_destination(
        self,
        *,
        profile: ContentProfile,
        platform: SocialPlatform,
        selection_token: str,
        external_account_id: str,
        redis: Redis,
    ) -> PlatformConnection:
        """Finalize the connection against one chosen destination."""
        pending_state = await pending.consume(redis, selection_token)

        # Re-verify at finalization, not only at callback: the caller has
        # already passed `require_profile_access` for this path profile, so
        # requiring the pending state to name the same profile closes the
        # replay path where a selection token minted for profile A is
        # presented on profile B's endpoint.
        if pending_state.profile_id != profile.id:
            raise StateProfileMismatchError(
                "Pending connection does not match the requested profile"
            )
        if pending_state.platform != platform:
            raise StateProfileMismatchError(
                "Pending connection does not match the requested platform"
            )

        destination = pending_state.find_destination(external_account_id)
        if destination is None:
            # Never trust a client-named destination: only one the platform
            # actually returned for this account may be persisted.
            raise DestinationNotAvailableError(
                "Selected destination is not one of the available destinations"
            )

        return await self._persist_connection(
            profile=profile,
            platform=platform,
            destination=destination,
            credentials=pending_state.credentials,
        )

    async def _persist_connection(
        self,
        *,
        profile: ContentProfile,
        platform: SocialPlatform,
        destination: Destination,
        credentials: UserCredentials,
    ) -> PlatformConnection:
        """Upsert the single `(profile_id, platform)` row.

        Reconnecting replaces the existing row's credentials in place rather
        than inserting a second one -- the unique constraint would reject a
        duplicate anyway, and replacing keeps the connection's identity
        (and any future FK to it) stable across reconnects.
        """
        # Declared per platform, never inferred from whether a token
        # happened to be present in the response -- inferring would let a
        # Page that returned no `access_token` silently fall through to
        # storing the account-wide USER token while labelling it
        # "account", which is precisely the blast radius this day avoids.
        destination_scoped = get_provider(platform).issues_destination_token

        if destination_scoped:
            if destination.access_token is None:
                raise MissingDestinationTokenError(
                    f"{platform} did not return a destination-scoped token for "
                    f"{destination.external_account_id}"
                )
            # Facebook/Instagram: the Page-scoped token. The user-level
            # token is discarded here and never persisted.
            access_token = destination.access_token
            refresh_token = None
            # A Page token derived from a long-lived user token does not
            # expire; there is nothing meaningful to store.
            expires_at = None
        else:
            # YouTube: Google issues no per-channel credential, so the
            # account-level token is what authorizes uploads to the chosen
            # channel. Recorded explicitly in metadata rather than left
            # ambiguous.
            access_token = credentials.access_token
            refresh_token = credentials.refresh_token
            expires_at = credentials.expires_at

        now = datetime.now(UTC)
        metadata = {
            "token_scope": "destination" if destination_scoped else "account",
            **destination.metadata,
        }

        connection = await self.repository.get_for_profile_platform(profile.id, platform)
        is_new = connection is None
        if is_new:
            connection = PlatformConnection(
                workspace_id=profile.workspace_id,
                profile_id=profile.id,
                platform=platform,
            )

        connection.external_account_id = destination.external_account_id
        connection.external_account_name = destination.external_account_name
        connection.access_token_encrypted = encrypt_token(access_token)
        connection.refresh_token_encrypted = encrypt_optional(refresh_token)
        connection.token_expires_at = expires_at
        connection.scopes_granted = credentials.scopes
        connection.status = ConnectionStatus.CONNECTED
        connection.connected_at = now
        connection.last_refreshed_at = None
        connection.connection_metadata = metadata

        # Every NOT NULL column is populated before the row is flushed --
        # a new connection is added only once it is complete.
        try:
            if is_new:
                await self.repository.create(connection)
            else:
                await self.repository.update(connection)
            await self.session.commit()
        except IntegrityError as error:
            # Two selections for the same (profile, platform) landing
            # together -- a double-clicked picker, or a retried request --
            # both see no existing row and both insert. The unique
            # constraint catches the second; normalize it to a domain
            # conflict rather than letting a raw DB error become a 500,
            # matching the Day 13 variation-selection precedent.
            await self.session.rollback()
            raise ConnectionConflictError(
                "This profile's connection for that platform was modified concurrently; retry"
            ) from error
        return connection

    # --- Reads -------------------------------------------------------------

    async def list_connections(self, profile_id: UUID) -> list[PlatformConnection]:
        return await self.repository.list_for_profile(profile_id)

    # --- Disconnect --------------------------------------------------------

    async def disconnect(
        self,
        *,
        profile: ContentProfile,
        platform: SocialPlatform,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Revoke with the platform where supported, then delete the row.

        The local credential is deleted whether or not revocation succeeds:
        a platform that is unreachable, or that refuses a Page-token-scoped
        revocation, must not leave us holding a live token. A hard delete,
        not a status flip -- see `PlatformConnectionRepository.delete`.
        """
        connection = await self.repository.get_for_profile_platform(profile.id, platform)
        if connection is None:
            raise ConnectionNotFoundError("Platform connection not found")

        provider = get_provider(platform)
        owns_client = client is None
        client = client or build_http_client()
        try:
            access_token = decrypt_token(connection.access_token_encrypted)
            revoked = await provider.revoke(access_token=access_token, client=client)
        except Exception:  # noqa: BLE001 - revocation is best-effort by design
            logger.warning(
                "platform_connection.revoke_failed",
                extra={"connection_id": str(connection.id), "platform": str(platform)},
            )
            revoked = False
        finally:
            if owns_client:
                await client.aclose()

        await self.repository.delete(connection)
        await self.session.commit()
        logger.info(
            "platform_connection.disconnected",
            extra={
                "profile_id": str(profile.id),
                "platform": str(platform),
                "platform_revoked": revoked,
            },
        )

    # --- Proactive refresh -------------------------------------------------

    async def refresh_connection(
        self, connection: PlatformConnection, *, client: httpx.AsyncClient | None = None
    ) -> bool:
        """Refresh one near-expiry connection.

        Returns True on success. On any failure the connection is marked
        `expired` rather than left looking healthy -- the user is told to
        reconnect now, instead of a publish silently failing later (see
        "AI Execution and Job Control" in the architecture doc: a failure
        gets a durable, visible state, never a silent one).
        """
        provider = get_provider(connection.platform)

        if connection.refresh_token_encrypted is None:
            # Nothing to refresh with (e.g. a Facebook/Instagram Page
            # token). If it has reached its expiry window anyway, it needs a
            # real reconnect, not a retry.
            await self._mark_expired(connection, reason="no_refresh_token")
            return False

        owns_client = client is None
        client = client or build_http_client()
        try:
            refreshed = await provider.refresh(
                refresh_token=decrypt_token(connection.refresh_token_encrypted), client=client
            )
        except Exception as error:  # noqa: BLE001 - every failure mode ends the same way
            logger.warning(
                "platform_connection.refresh_failed",
                extra={
                    "connection_id": str(connection.id),
                    "platform": str(connection.platform),
                    "error": type(error).__name__,
                },
            )
            await self._mark_expired(connection, reason="refresh_failed")
            return False
        finally:
            if owns_client:
                await client.aclose()

        connection.access_token_encrypted = encrypt_token(refreshed.access_token)
        if refreshed.refresh_token is not None:
            connection.refresh_token_encrypted = encrypt_token(refreshed.refresh_token)
        connection.token_expires_at = refreshed.expires_at
        connection.status = ConnectionStatus.CONNECTED
        connection.last_refreshed_at = datetime.now(UTC)
        await self.repository.update(connection)
        await self.session.commit()
        return True

    async def _mark_expired(self, connection: PlatformConnection, *, reason: str) -> None:
        connection.status = ConnectionStatus.EXPIRED
        connection.connection_metadata = {
            **(connection.connection_metadata or {}),
            "expired_reason": reason,
            "expired_at": datetime.now(UTC).isoformat(),
        }
        await self.repository.update(connection)
        await self.session.commit()

    async def list_due_for_refresh(self) -> list[PlatformConnection]:
        due_before = datetime.now(UTC) + timedelta(
            seconds=settings.platform_connection_refresh_threshold_seconds
        )
        return await self.repository.list_due_for_refresh(
            due_before=due_before, limit=settings.platform_connection_refresh_batch_size
        )
