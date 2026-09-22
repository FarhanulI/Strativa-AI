"""Add platform_connections

Revision ID: y8z9a0b1c2
Revises: x7y8z9a0b1

Day 23 - Platform Connections (OAuth for YouTube, Facebook & Instagram).

Two constraint choices worth stating explicitly:

* The unique constraint is on `(profile_id, platform)`, NOT
  `(workspace_id, platform)`. Under Model A a workspace holds several
  ContentProfiles, and two of them may legitimately publish to two
  different Pages/Channels through the same underlying social login.
  Scoping uniqueness to the workspace would make that impossible.
* `(status, token_expires_at)` is indexed for the proactive-refresh job's
  due-item query.

Token columns are `Text`, not `String(n)`: they hold envelope-encrypted
ciphertext (see app/platform_connections/crypto.py), which is
substantially longer than the underlying token and varies with the
scheme, so a fixed width would be a migration liability at the next
rotation.

Reversible: `downgrade()` drops the table and its enum types.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, JSONB

revision: str = "y8z9a0b1c2"
down_revision: str | None = "x7y8z9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLAlchemy's `Enum(PyEnum)` persists the member NAME, not its value, so
# these are the uppercase names -- matching what the ORM actually binds
# ('YOUTUBE', not 'youtube') and the precedent set by `o8p9q0r1s2`
# (jobstatus) and `e7f8a9b0c1d2`. Lowercase labels here would create a
# Postgres type that rejects every insert the application makes, and the
# SQLite test suite could not catch it (SQLite renders Enum as VARCHAR +
# CHECK built from the model, so both sides would agree there).
_PLATFORM_VALUES = ("YOUTUBE", "FACEBOOK", "INSTAGRAM")
_STATUS_VALUES = ("CONNECTED", "DISCONNECTED", "EXPIRED", "REVOKED")


def upgrade() -> None:
    bind = op.get_bind()
    platform_enum = ENUM(*_PLATFORM_VALUES, name="socialplatform", create_type=False)
    status_enum = ENUM(*_STATUS_VALUES, name="connectionstatus", create_type=False)
    platform_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)

    json_type = sa.JSON().with_variant(JSONB, "postgresql")

    op.create_table(
        "platform_connections",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("content_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("external_account_name", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes_granted", json_type, nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="CONNECTED"),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "profile_id", "platform", name="uq_platform_connections_profile_platform"
        ),
    )

    op.create_index(
        "ix_platform_connections_workspace_id", "platform_connections", ["workspace_id"]
    )
    op.create_index("ix_platform_connections_profile_id", "platform_connections", ["profile_id"])
    op.create_index(
        "ix_platform_connections_status_token_expires_at",
        "platform_connections",
        ["status", "token_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_connections_status_token_expires_at", "platform_connections")
    op.drop_index("ix_platform_connections_profile_id", "platform_connections")
    op.drop_index("ix_platform_connections_workspace_id", "platform_connections")
    op.drop_table("platform_connections")

    bind = op.get_bind()
    sa.Enum(name="connectionstatus").drop(bind, checkfirst=True)
    sa.Enum(name="socialplatform").drop(bind, checkfirst=True)
