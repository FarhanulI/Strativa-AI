"""Pending-connection state: the gap between token exchange and
destination selection.

After the OAuth callback we hold a user-level token and a list of
destinations, but we deliberately do **not** yet have a
`PlatformConnection` -- the caller still has to say which Page/Channel this
profile publishes to. That intermediate state has to live somewhere for a
few minutes, and Redis (the Day 15 connection) is the right place for a
reason: it expires on its own.

An abandoned OAuth attempt -- the user closes the tab at the
destination-picker -- therefore leaves no dangling credential anywhere. The
key simply lapses. Nothing is written to Postgres until a destination is
chosen, and nothing has to be cleaned up if one never is.

The user-level token and every per-destination token in this blob are
envelope-encrypted with the same scheme as the final stored credential
(`app/platform_connections/crypto.py`), not stored as plaintext JSON --
"it's only in Redis for ten minutes" is not a reason to hold a live
credential in the clear.

The selection token is single-use: `consume` deletes the key atomically as
it reads it, so a replayed selection token finds nothing.
"""

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.platform_connections.crypto import decrypt_token, encrypt_token
from app.platform_connections.models import SocialPlatform
from app.platform_connections.oauth.base import Destination, UserCredentials

_KEY_PREFIX = "platform_connection:pending:"


class PendingConnectionNotFoundError(ValueError):
    """Raised when a selection token is unknown, already used, or expired."""


@dataclass(frozen=True)
class PendingConnection:
    """The decrypted pending state. Never logged, never serialized to a
    response -- only `destinations` (which hold no credentials once
    `to_public_destinations` has stripped them) reaches the client.
    """

    profile_id: UUID
    workspace_id: UUID
    platform: SocialPlatform
    credentials: UserCredentials
    destinations: list[Destination]

    def find_destination(self, external_account_id: str) -> Destination | None:
        for destination in self.destinations:
            if destination.external_account_id == external_account_id:
                return destination
        return None


def redis_key(selection_token: str) -> str:
    """The Redis key for a pending connection. Public so tests can assert on
    TTL/ciphertext-at-rest directly against Redis, without this module
    growing read helpers that production code never calls.
    """
    return f"{_KEY_PREFIX}{selection_token}"


_key = redis_key


async def store(
    redis: Redis,
    *,
    profile_id: UUID,
    workspace_id: UUID,
    platform: SocialPlatform,
    credentials: UserCredentials,
    destinations: list[Destination],
) -> tuple[str, int]:
    """Park the pending state under a fresh one-time selection token.

    Returns `(selection_token, ttl_seconds)`. Every token in the blob is
    encrypted before it goes near Redis.
    """
    selection_token = secrets.token_urlsafe(32)
    ttl = settings.oauth_pending_connection_ttl_seconds

    payload: dict[str, Any] = {
        "profile_id": str(profile_id),
        "workspace_id": str(workspace_id),
        "platform": str(platform),
        "user_access_token": encrypt_token(credentials.access_token),
        "user_refresh_token": (
            encrypt_token(credentials.refresh_token) if credentials.refresh_token else None
        ),
        "user_token_expires_at": (
            credentials.expires_at.isoformat() if credentials.expires_at else None
        ),
        "scopes": credentials.scopes,
        "destinations": [
            {
                "external_account_id": destination.external_account_id,
                "external_account_name": destination.external_account_name,
                "access_token": (
                    encrypt_token(destination.access_token) if destination.access_token else None
                ),
                "metadata": destination.metadata,
            }
            for destination in destinations
        ],
    }

    await redis.set(_key(selection_token), json.dumps(payload), ex=ttl)
    return selection_token, ttl


async def consume(redis: Redis, selection_token: str) -> PendingConnection:
    """Read and delete the pending state in one shot.

    `GETDEL` makes the selection token genuinely single-use: a second
    attempt with the same token -- a replay -- finds nothing, even if it
    arrives microseconds later.
    """
    raw = await redis.getdel(_key(selection_token))
    if raw is None:
        raise PendingConnectionNotFoundError(
            "Pending connection not found or expired; restart the connection flow"
        )
    return _decode(raw)


def _decode(raw: str | bytes) -> PendingConnection:
    payload = json.loads(raw)
    expires_at = payload.get("user_token_expires_at")

    return PendingConnection(
        profile_id=UUID(payload["profile_id"]),
        workspace_id=UUID(payload["workspace_id"]),
        platform=SocialPlatform(payload["platform"]),
        credentials=UserCredentials(
            access_token=decrypt_token(payload["user_access_token"]),
            refresh_token=(
                decrypt_token(payload["user_refresh_token"])
                if payload.get("user_refresh_token")
                else None
            ),
            expires_at=(datetime.fromisoformat(expires_at).astimezone(UTC) if expires_at else None),
            scopes=payload.get("scopes") or [],
        ),
        destinations=[
            Destination(
                external_account_id=item["external_account_id"],
                external_account_name=item.get("external_account_name"),
                access_token=(
                    decrypt_token(item["access_token"]) if item.get("access_token") else None
                ),
                metadata=item.get("metadata") or {},
            )
            for item in payload.get("destinations", [])
        ],
    )
