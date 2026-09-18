"""PlatformConnection -- one ContentProfile's authorized publishing
destination on one social platform (Day 23).

The central modelling point of this day: **one OAuth login is not one
publishable destination.** A person has one Facebook login but may
administer several Pages; one Google login but may manage several YouTube
channels (including Brand Account channels); Instagram publishing runs
through a Business Account linked to a *specific* Page. Because a Workspace
can hold several `ContentProfile`s (Model A), two profiles in the same
workspace may legitimately need to publish to two *different*
Pages/Channels through the *same* underlying social login.

So this row does not represent "the user connected Facebook." It represents
"this profile publishes to this specific Page," and
`external_account_id` is always that specific destination's id -- a Page
ID, a YouTube Channel ID, or an Instagram Business Account ID -- never the
top-level user/account id the OAuth login authenticated as.

That is also why the uniqueness rule is `(profile_id, platform)` and not
`(workspace_id, platform)`: two profiles under one workspace each hold
their own independent connection.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SocialPlatform(StrEnum):
    """Platforms with a real OAuth implementation as of Day 23.

    TikTok/LinkedIn/X are explicitly out of scope for this day and are
    deliberately absent rather than declared-but-unimplemented.
    """

    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PlatformConnection(Base):
    __tablename__ = "platform_connections"
    __table_args__ = (
        # Model A: the constraint is per PROFILE, not per workspace -- two
        # profiles in one workspace can each connect the same platform, to
        # different destinations. Reconnecting replaces this row rather than
        # adding a second one.
        UniqueConstraint("profile_id", "platform", name="uq_platform_connections_profile_platform"),
        # Serves the proactive-refresh job's due-item query
        # (status = connected AND token_expires_at <= now + threshold).
        Index("ix_platform_connections_status_token_expires_at", "status", "token_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[SocialPlatform] = mapped_column(SqlEnum(SocialPlatform), nullable=False)

    # The SPECIFIC destination this connection publishes to -- Page ID /
    # Channel ID / Instagram Business Account ID. Never the top-level
    # user/account id (see the module docstring).
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Envelope-encrypted at rest (app/platform_connections/crypto.py). Named
    # `_encrypted` rather than the bare `access_token`/`refresh_token` so no
    # call site can mistake the column for plaintext. For Facebook/Instagram
    # this holds the PAGE-scoped token, not the user token -- the user token
    # is never persisted at all, it lives only in the short-TTL Redis
    # pending state and is dropped once a destination is selected.
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable on purpose, and the per-platform lifecycle genuinely differs:
    # Google issues a long-lived refresh token alongside a ~1h access token,
    # whereas a Facebook/Instagram Page token derived from a long-lived user
    # token does not expire and has no refresh token at all.
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    json_type = JSON().with_variant(JSONB, "postgresql")
    scopes_granted: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)

    status: Mapped[ConnectionStatus] = mapped_column(
        SqlEnum(ConnectionStatus), nullable=False, default=ConnectionStatus.CONNECTED
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Lineage/diagnostic only -- never a copy of a top-level column's value,
    # and never any credential material.
    connection_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """Deliberately excludes every token column -- a repr() of this row
        must never be able to put a credential into a log line or traceback.
        """
        return (
            f"<PlatformConnection id={self.id} profile_id={self.profile_id} "
            f"platform={self.platform} external_account_id={self.external_account_id} "
            f"status={self.status}>"
        )
