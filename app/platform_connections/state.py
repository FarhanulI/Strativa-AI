"""Signed, expiring CSRF `state` parameter for the OAuth authorize step.

The `state` round-trips through the platform's consent screen, so it is
attacker-visible and attacker-replayable. It is therefore HMAC-signed
(never encrypted-and-trusted, never a bare random string looked up in a
table) and carries an expiry.

It encodes the target `profile_id` because the destination-selection step
that runs *after* the callback needs to know which profile the connection
is being finalized against.

Crucially, a valid signature here proves only "this system issued this
state" -- it proves nothing about who is presenting it now. The callback
and selection endpoints therefore *also* run Day 21's
`require_profile_access` against the path `profile_id` and cross-check the
state-encoded `profile_id` against it, so a forged or replayed state
cannot attach a connection to a profile the caller doesn't own. See
`app/platform_connections/router.py`.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.platform_connections.models import SocialPlatform


class InvalidOAuthStateError(ValueError):
    """Raised when a `state` fails signature, format, or expiry validation."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str) -> str:
    signature = hmac.new(
        settings.resolved_oauth_state_secret.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64e(signature)


def issue_state(
    *,
    profile_id: UUID,
    workspace_id: UUID,
    platform: SocialPlatform,
    redirect_uri: str,
    now: float | None = None,
) -> str:
    """Build `<b64url(payload)>.<b64url(hmac)>`.

    `nonce` makes two states issued in the same second distinct, so a state
    is never accidentally reusable just because its payload repeats.
    """
    issued_at = time.time() if now is None else now
    payload = {
        "profile_id": str(profile_id),
        "workspace_id": str(workspace_id),
        "platform": str(platform),
        "redirect_uri": redirect_uri,
        "nonce": secrets.token_urlsafe(16),
        "exp": issued_at + settings.oauth_state_ttl_seconds,
    }
    encoded = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{encoded}.{_sign(encoded)}"


def verify_state(state: str, *, now: float | None = None) -> dict[str, Any]:
    """Validate signature and expiry, returning the decoded payload.

    Signature comparison is constant-time. Every failure mode raises the
    same exception type with a deliberately non-specific message -- an
    attacker probing the endpoint learns nothing about *which* check
    failed.
    """
    if not state or state.count(".") != 1:
        raise InvalidOAuthStateError("Invalid OAuth state")

    encoded, signature = state.split(".")
    if not hmac.compare_digest(_sign(encoded), signature):
        raise InvalidOAuthStateError("Invalid OAuth state")

    try:
        payload = json.loads(_b64d(encoded))
    except (ValueError, TypeError) as error:
        raise InvalidOAuthStateError("Invalid OAuth state") from error

    if not isinstance(payload, dict) or "exp" not in payload:
        raise InvalidOAuthStateError("Invalid OAuth state")

    current = time.time() if now is None else now
    if float(payload["exp"]) < current:
        raise InvalidOAuthStateError("Invalid OAuth state")

    return payload
