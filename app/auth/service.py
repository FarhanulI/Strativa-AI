"""Authentication service: login, refresh (with mandatory rotation),
logout (revocation), and password reset.

Day 20 scope note: this authenticates an EXISTING user against an
EXISTING workspace only. There is no `register`/`create_user` here --
signup and workspace auto-provisioning are a separate, already-planned
follow-up day (see docs/development/day-20.md). `WorkspaceMember.user_id`
is a bare, unenforced `String(255)` (Day 21 adds the foreign key), so the
membership lookup here is a best-effort string match used only to build
the JWT's `workspace_ids` fast-path hint -- never treated as
authorization.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token, encode_access_token
from app.auth.models import PasswordResetToken, RefreshToken, User
from app.auth.repository import (
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.auth.security import (
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.models.workspace_member import WorkspaceMember

logger = structlog.get_logger(__name__)

# Identical message for "unknown email" and "wrong password" so the
# response cannot be used to enumerate registered accounts.
_INVALID_CREDENTIALS_MESSAGE = "Invalid email or password"


def _as_aware_utc(dt: datetime) -> datetime:
    """SQLite (used in tests) does not round-trip timezone info on
    `DateTime(timezone=True)` columns, returning naive datetimes on read;
    Postgres does. All timestamps in this module are UTC, so a naive value
    read back from the DB is assumed to already be UTC.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class InvalidResetTokenError(Exception):
    pass


class AuthService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)

    async def _workspace_ids_for_user(self, user_id: uuid.UUID) -> list[str]:
        """Best-effort fast-path hint only -- see module docstring."""
        result = await self.session.execute(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == str(user_id))
        )
        return [str(row) for row in result.scalars()]

    async def _issue_token_pair(self, user: User) -> tuple[str, str, int]:
        session_id = uuid.uuid4()
        workspace_ids = await self._workspace_ids_for_user(user.id)
        access_token, _jti, exp = encode_access_token(user.id, session_id, workspace_ids)

        raw_refresh_token = generate_opaque_token()
        now = datetime.now(UTC)
        refresh_expires_at = now + timedelta(days=settings.jwt_refresh_token_ttl_days)
        await self.refresh_tokens.create(
            RefreshToken(
                user_id=user.id,
                session_id=session_id,
                token_hash=hash_opaque_token(raw_refresh_token),
                expires_at=refresh_expires_at,
            )
        )
        await self.session.commit()

        expires_in = int((exp - now).total_seconds())
        return access_token, raw_refresh_token, expires_in

    async def login(self, email: str, password: str) -> tuple[str, str, int]:
        user = await self.users.get_by_email(email)
        if user is None:
            # Run the hash verification anyway against a fixed dummy hash
            # so a wrong-email response takes roughly the same time as a
            # wrong-password response (no email-existence timing signal).
            verify_password(password, _DUMMY_HASH)
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

        return await self._issue_token_pair(user)

    async def refresh(self, raw_refresh_token: str) -> tuple[str, str, int]:
        token_hash = hash_opaque_token(raw_refresh_token)
        stored = await self.refresh_tokens.get_by_token_hash(token_hash)
        now = datetime.now(UTC)

        if stored is None:
            raise InvalidRefreshTokenError("Refresh token not recognized")

        if stored.revoked_at is not None:
            # Reuse of an already-rotated (or already-logged-out) token is
            # treated as a possible compromise: the entire session family
            # is revoked, not just this row, so a leaked-but-rotated token
            # can't be replayed to keep a stolen session alive.
            await self.refresh_tokens.revoke_session(stored.session_id, now)
            await self.session.commit()
            raise InvalidRefreshTokenError("Refresh token has already been used")

        if _as_aware_utc(stored.expires_at) < now:
            raise InvalidRefreshTokenError("Refresh token has expired")

        user = await self.users.get_by_id(stored.user_id)
        if user is None:
            raise InvalidRefreshTokenError("Refresh token not recognized")

        # Rotation: the presented token is revoked and a new pair is
        # issued in the same session so logout/reuse-detection can still
        # reason about "this session" across rotations.
        await self.refresh_tokens.revoke(stored, now)

        workspace_ids = await self._workspace_ids_for_user(user.id)
        access_token, _jti, exp = encode_access_token(user.id, stored.session_id, workspace_ids)

        raw_new_refresh_token = generate_opaque_token()
        refresh_expires_at = now + timedelta(days=settings.jwt_refresh_token_ttl_days)
        await self.refresh_tokens.create(
            RefreshToken(
                user_id=user.id,
                session_id=stored.session_id,
                token_hash=hash_opaque_token(raw_new_refresh_token),
                expires_at=refresh_expires_at,
            )
        )
        await self.session.commit()

        expires_in = int((exp - now).total_seconds())
        return access_token, raw_new_refresh_token, expires_in

    async def logout(self, access_token: str, raw_refresh_token: str | None) -> None:
        """Revokes the access token's `jti` immediately (Redis, TTL = its
        remaining validity) and, if a refresh token is presented, revokes
        its entire session so a subsequent refresh attempt also fails --
        without this, logout would only block the already-short-lived
        access token while a valid refresh token could still mint a new
        one.
        """
        claims = decode_access_token(access_token)
        now = datetime.now(UTC)
        remaining_seconds = max(int((claims.exp - now).total_seconds()), 0)
        if remaining_seconds > 0:
            await self.redis.set(f"revoked_jti:{claims.jti}", "1", ex=remaining_seconds)

        if raw_refresh_token is not None:
            stored = await self.refresh_tokens.get_by_token_hash(
                hash_opaque_token(raw_refresh_token)
            )
            if stored is not None and stored.revoked_at is None:
                await self.refresh_tokens.revoke_session(stored.session_id, now)
        else:
            await self.refresh_tokens.revoke_session(uuid.UUID(claims.sid), now)

        await self.session.commit()

    async def request_password_reset(self, email: str) -> str | None:
        """Returns the raw reset token for the stub email-delivery path
        (see `send_password_reset_email`) and for direct service-level
        testing; the HTTP layer must never echo this back in the response
        (would leak whether an email is registered) -- see
        app/api/v1/auth.py.
        """
        user = await self.users.get_by_email(email)
        if user is None:
            return None

        raw_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.password_reset_token_ttl_minutes
        )
        await self.reset_tokens.create(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_opaque_token(raw_token),
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        send_password_reset_email(email, raw_token)
        return raw_token

    async def confirm_password_reset(self, raw_token: str, new_password: str) -> None:
        stored = await self.reset_tokens.get_by_token_hash(hash_opaque_token(raw_token))
        now = datetime.now(UTC)

        if stored is None:
            raise InvalidResetTokenError("Reset token not recognized")
        if stored.used_at is not None:
            raise InvalidResetTokenError("Reset token has already been used")
        if _as_aware_utc(stored.expires_at) < now:
            raise InvalidResetTokenError("Reset token has expired")

        user = await self.users.get_by_id(stored.user_id)
        if user is None:
            raise InvalidResetTokenError("Reset token not recognized")

        user.hashed_password = hash_password(new_password)
        stored.used_at = now
        await self.session.commit()


def send_password_reset_email(email: str, raw_token: str) -> None:
    """STUB: no email provider is configured anywhere in this stack yet.

    This logs the reset token instead of emailing it, which is acceptable
    only for local development/tests -- it must be replaced with a real
    email provider integration before this flow is exposed outside a
    controlled environment (raw reset tokens are as sensitive as a
    password and must not otherwise appear in logs).
    """
    logger.info(
        "password_reset_email_stub",
        email=email,
        reset_token=raw_token,
        note="no email provider configured; logging for local/dev use only",
    )


# A precomputed argon2 hash of an unused, random plaintext -- used only to
# equalize the timing of an unknown-email login attempt against a real
# verify_password call, never to authenticate anything.
_DUMMY_HASH = hash_password(generate_opaque_token())
