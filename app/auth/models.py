import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """Credential identity for an existing, pre-seeded platform user.

    Day 20 (Authentication Foundation) authenticates an EXISTING user
    against an EXISTING workspace only -- there is no signup endpoint.
    `id` is a UUID (not an autoincrement int) specifically so a future
    `WorkspaceMember.user_id -> User.id` foreign key (Day 21 -
    Ownership-Chain Enforcement Retrofit) needs no type-conversion
    migration; `WorkspaceMember.user_id` remains an unenforced
    `String(255)` until that day.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class RefreshToken(Base):
    """Server-side record of an issued refresh token.

    Only a hash of the token is stored, never the plaintext (see
    docs/development/day-20.md). `session_id` groups the chain of tokens
    produced by rotation for one login, so logout and reuse detection can
    act on "this session" rather than a single row. `revoked_at` is set the
    instant a token is rotated (used to detect reuse of a stale token) or
    explicitly revoked at logout.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(Base):
    """Single-use, time-limited token issued for a password reset request.

    Only a hash of the token is stored. `used_at` is set on successful
    confirmation so the same token cannot be replayed.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
