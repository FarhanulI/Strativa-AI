"""JWT issuance and verification for access tokens.

Refresh tokens are NOT JWTs (see app/auth/security.py) -- only the short-
lived access token is a signed JWT, carrying `sub` (user id), `jti`
(unique per access token, used for Redis revocation), `sid` (session id,
shared with the refresh-token family issued alongside it), `iat`/`exp`,
and `workspace_ids` (a fast-path hint only).

Per docs/product/product-architecture.md "Identity, Tenancy, and
Authorization" and this day's explicit scope: `workspace_ids` must never
be treated as authorization by itself. It exists so a caller can be
told which workspaces it plausibly belongs to without a DB round trip;
the authoritative check for any specific resource still queries the
database (and, until Day 21 ships, nothing does that check at all -- see
docs/development/day-20.md).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Request

from app.core.config import settings

ALGORITHM_CLAIM_LEEWAY_SECONDS = 0


@dataclass(frozen=True)
class AccessTokenClaims:
    sub: str
    jti: str
    sid: str
    iat: datetime
    exp: datetime
    workspace_ids: list[str]


class InvalidTokenError(Exception):
    """Raised for any malformed, expired, or badly-signed access token."""


def encode_access_token(
    user_id: uuid.UUID, session_id: uuid.UUID, workspace_ids: list[str]
) -> tuple[str, str, datetime]:
    """Returns (token, jti, exp) -- jti/exp are also returned directly so
    callers (login/refresh) don't need to immediately re-decode the token
    they just minted.
    """
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "sid": str(session_id),
        "iat": now,
        "exp": exp,
        "workspace_ids": workspace_ids,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, exp


def decode_access_token(token: str) -> AccessTokenClaims:
    """Verifies signature and expiry only -- does NOT check the Redis
    revocation list. Callers that need revocation-aware verification must
    use app.auth.dependencies.get_current_user instead; this function is
    also used by the rate-limit middleware, which deliberately makes no
    authorization decision (see docs/development/day-20.md Section 2).
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    try:
        return AccessTokenClaims(
            sub=payload["sub"],
            jti=payload["jti"],
            sid=payload["sid"],
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            workspace_ids=payload.get("workspace_ids", []),
        )
    except KeyError as exc:
        raise InvalidTokenError(f"missing claim: {exc}") from exc


def extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header or not header.startswith("Bearer "):
        return None
    return header.removeprefix("Bearer ").strip() or None


def try_get_request_identity(request: Request) -> str | None:
    """Best-effort authenticated identity for rate-limit bucketing only.

    Decodes and verifies signature/expiry but never checks revocation and
    never raises -- an invalid/missing/expired token simply yields no
    identity, so the caller (the rate-limit middleware) falls back to an
    anonymous bucket. This is the Day 15 rate limiter's post-Day-20
    identity source (see app/infrastructure/ratelimit/middleware.py);
    it makes no authorization decision.
    """
    token = extract_bearer_token(request)
    if not token:
        return None
    try:
        claims = decode_access_token(token)
    except InvalidTokenError:
        return None
    return f"user:{claims.sub}"
