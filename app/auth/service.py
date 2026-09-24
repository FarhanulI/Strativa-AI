"""Authentication service: login, refresh (with mandatory rotation),
logout (revocation), and password reset.

Day 20 scope note: this authenticates an EXISTING user against an
EXISTING workspace only. There is no `register`/`create_user` here --
signup and workspace auto-provisioning are a separate, already-planned
follow-up day (see docs/development/day-20.md). The membership lookup
here only builds the JWT's `workspace_ids` fast-path hint -- it is never
treated as authorization (see app/authz/dependencies.py for the real,
Day 21 ownership check).
"""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple, NoReturn

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from app.models.workspace import Workspace, WorkspaceOnboardingStatus
from app.models.workspace_member import WorkspaceMember, WorkspaceRole

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


class EmailAlreadyRegisteredError(Exception):
    pass


class WorkspaceSlugGenerationError(Exception):
    """Raised when repeated random-suffix collisions on `Workspace.slug`
    prevent `register` from provisioning a unique workspace after
    `_MAX_SLUG_ATTEMPTS` tries. Distinct from `EmailAlreadyRegisteredError`
    so callers don't misreport an available email as taken -- see
    `_extract_constraint_name`.
    """

    pass


_MAX_SLUG_ATTEMPTS = 3


class RegisterResult(NamedTuple):
    access_token: str
    refresh_token: str
    expires_in: int
    workspace_id: uuid.UUID
    workspace_onboarding_status: WorkspaceOnboardingStatus


class LoginResult(NamedTuple):
    access_token: str
    refresh_token: str
    expires_in: int
    # None only if the authenticated user has no workspace membership at
    # all -- shouldn't happen for anything created via `register` (which
    # always provisions one), but login predates register (Day 20) and
    # doesn't assume every credential-valid user has one.
    workspace_id: uuid.UUID | None
    workspace_onboarding_status: WorkspaceOnboardingStatus | None


def _slug_base(email: str) -> str:
    """Derives a URL-safe slug fragment from an email's local part -- used
    only as a human-readable prefix; uniqueness comes from the random
    suffix appended in `_generate_workspace_slug`, not from this value.
    """
    local_part = email.split("@", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", local_part).strip("-")
    return slug or "workspace"


def _generate_workspace_slug(email: str) -> str:
    return f"{_slug_base(email)}-{uuid.uuid4().hex[:8]}"


def _extract_constraint_name(err: IntegrityError) -> str:
    """Best-effort name of the DB constraint/index that raised `err`.

    On asyncpg, the driver-native error exposes the constraint name via
    `err.orig.diag.constraint_name`. That attribute chain isn't guaranteed
    across drivers/error shapes, so this falls back to the string form of
    the original error (e.g. SQLite's "UNIQUE constraint failed:
    users.email"), which still contains the offending column name for the
    substring checks callers do against this result.
    """
    try:
        constraint_name = err.orig.diag.constraint_name  # type: ignore[union-attr]
    except AttributeError:
        return str(err.orig)
    return constraint_name or str(err.orig)


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
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
        )
        return [str(row) for row in result.scalars()]

    async def _primary_workspace_summary(
        self, user_id: uuid.UUID
    ) -> tuple[uuid.UUID, WorkspaceOnboardingStatus] | None:
        """Returns (workspace_id, onboarding_status) for the user's first
        workspace membership, or None if they have none.

        Used by `login` so the frontend gets onboarding-routing info in
        the same response instead of a follow-up call. `register` doesn't
        need this: it already holds the just-created `Workspace` object
        in memory from the same transaction, so there's nothing to query.
        """
        result = await self.session.execute(
            select(Workspace.id, Workspace.onboarding_status)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(WorkspaceMember.created_at)
            .limit(1)
        )
        row = result.first()
        return (row.id, row.onboarding_status) if row is not None else None

    async def _issue_token_pair(self, user: User, *, commit: bool = True) -> tuple[str, str, int]:
        """Builds and persists a new access/refresh token pair for `user`.

        `commit` defaults to True (the login/refresh behavior). `register`
        passes `commit=False` so the RefreshToken insert lands in the same
        transaction/commit as the User/Workspace/WorkspaceMember it just
        created, rather than a second, separately-committable transaction
        (see module docstring for why that separation was a problem).
        """
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
        if commit:
            await self.session.commit()

        expires_in = int((exp - now).total_seconds())
        return access_token, raw_refresh_token, expires_in

    async def register(self, email: str, password: str) -> RegisterResult:
        """Creates a User, auto-provisions a Workspace with that user as its
        sole owning WorkspaceMember, sets the new workspace's
        onboarding_status to NOT_STARTED, and issues a token pair --
        all committed in a single transaction -- see docs/development/day-22.md.

        Duplicate-email rejection is enumeration-resistant the same way
        Day 20's login is: a pre-check gives a fast, clear rejection for
        the common case, and an `IntegrityError` from a genuine race
        (two concurrent registrations for the same email) is normalized
        into the same `EmailAlreadyRegisteredError` rather than leaking a
        raw database error.

        `Workspace.slug` is also unique, so a random-suffix collision on
        it (unrelated to the email) is retried with a freshly generated
        slug up to `_MAX_SLUG_ATTEMPTS` times rather than being
        misreported as a taken email.
        """
        normalized_email = email.lower()
        existing = await self.users.get_by_email(normalized_email)
        if existing is not None:
            raise EmailAlreadyRegisteredError("An account with this email already exists")

        hashed_password = hash_password(password)

        for attempt in range(1, _MAX_SLUG_ATTEMPTS + 1):
            user = User(email=normalized_email, hashed_password=hashed_password)
            workspace = Workspace(
                name=f"{_slug_base(normalized_email)}'s Workspace",
                slug=_generate_workspace_slug(normalized_email),
                onboarding_status=WorkspaceOnboardingStatus.NOT_STARTED,
            )
            self.session.add(user)
            self.session.add(workspace)
            try:
                await self.session.flush()
            except IntegrityError as err:
                await self.session.rollback()
                if self._is_retryable_slug_collision(err, attempt):
                    continue
                self._raise_registration_error(err)

            self.session.add(
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role=WorkspaceRole.OWNER,
                )
            )
            access_token, raw_refresh_token, expires_in = await self._issue_token_pair(
                user, commit=False
            )

            try:
                await self.session.commit()
            except IntegrityError as err:
                await self.session.rollback()
                if self._is_retryable_slug_collision(err, attempt):
                    continue
                self._raise_registration_error(err)

            return RegisterResult(
                access_token=access_token,
                refresh_token=raw_refresh_token,
                expires_in=expires_in,
                workspace_id=workspace.id,
                workspace_onboarding_status=workspace.onboarding_status,
            )

        raise WorkspaceSlugGenerationError(
            "Could not generate a unique workspace, please try again"
        )

    @staticmethod
    def _is_retryable_slug_collision(err: IntegrityError, attempt: int) -> bool:
        constraint_name = _extract_constraint_name(err)
        return "slug" in constraint_name and attempt < _MAX_SLUG_ATTEMPTS

    @staticmethod
    def _raise_registration_error(err: IntegrityError) -> NoReturn:
        """Classifies and raises a flush/commit `IntegrityError` from
        `register`.

        An email-constraint violation raises `EmailAlreadyRegisteredError`;
        a slug-constraint violation that has exhausted its retries raises
        `WorkspaceSlugGenerationError`; anything else re-raises the
        original `IntegrityError` unchanged rather than misreporting it as
        either case.
        """
        constraint_name = _extract_constraint_name(err)
        if "email" in constraint_name:
            raise EmailAlreadyRegisteredError("An account with this email already exists") from err
        if "slug" in constraint_name:
            raise WorkspaceSlugGenerationError(
                "Could not generate a unique workspace, please try again"
            ) from err
        raise err

    async def login(self, email: str, password: str) -> LoginResult:
        user = await self.users.get_by_email(email)
        if user is None:
            # Run the hash verification anyway against a fixed dummy hash
            # so a wrong-email response takes roughly the same time as a
            # wrong-password response (no email-existence timing signal).
            verify_password(password, _DUMMY_HASH)
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

        access_token, raw_refresh_token, expires_in = await self._issue_token_pair(user)
        workspace = await self._primary_workspace_summary(user.id)
        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=expires_in,
            workspace_id=workspace[0] if workspace is not None else None,
            workspace_onboarding_status=workspace[1] if workspace is not None else None,
        )

    async def refresh(self, raw_refresh_token: str) -> tuple[str, str, int]:
        """Validates and rotates a refresh token.

        The initial `get_by_token_hash` read exists only to produce a
        precise error message for the not-found/expired cases -- it must
        NOT be used to decide whether this request is allowed to rotate
        the token, since two concurrent requests presenting the same
        token could both read `revoked_at is None` before either commits
        (a TOCTOU race). The actual "am I allowed to rotate this row"
        decision is made exclusively by the atomic
        `claim_for_rotation` conditional UPDATE below, which only one
        concurrent caller can ever win for a given row.
        """
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

        # Claim-then-act: only one concurrent caller can flip
        # revoked_at from NULL to non-NULL for this row. If we lose that
        # race, another request rotated (or reused) it between our read
        # above and this claim -- handled identically to a genuine
        # replay (whole session revoked), since the two are
        # indistinguishable from a security standpoint.
        claimed = await self.refresh_tokens.claim_for_rotation(token_hash, now)
        if claimed is None:
            await self.refresh_tokens.revoke_session(stored.session_id, now)
            await self.session.commit()
            raise InvalidRefreshTokenError("Refresh token has already been used")

        user = await self.users.get_by_id(claimed.user_id)
        if user is None:
            raise InvalidRefreshTokenError("Refresh token not recognized")

        workspace_ids = await self._workspace_ids_for_user(user.id)
        access_token, _jti, exp = encode_access_token(user.id, claimed.session_id, workspace_ids)

        raw_new_refresh_token = generate_opaque_token()
        refresh_expires_at = now + timedelta(days=settings.jwt_refresh_token_ttl_days)
        await self.refresh_tokens.create(
            RefreshToken(
                user_id=user.id,
                session_id=claimed.session_id,
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
