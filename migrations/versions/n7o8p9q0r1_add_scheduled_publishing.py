"""Add scheduled and cancelled publishing support to published content

Revision ID: n7o8p9q0r1
Revises: m6n7o8p9q0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n7o8p9q0r1"
down_revision: str | None = "m6n7o8p9q0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE publishstatus ADD VALUE IF NOT EXISTS 'SCHEDULED'")
    op.execute("ALTER TYPE publishstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    op.add_column(
        "published_content",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_published_content_scheduled_at"), "published_content", ["scheduled_at"]
    )
    op.create_index(
        "ix_published_content_status_scheduled_at",
        "published_content",
        ["status", "scheduled_at"],
    )

    op.alter_column(
        "published_content",
        "published_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "published_content",
        "published_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    op.drop_index("ix_published_content_status_scheduled_at", table_name="published_content")
    op.drop_index(op.f("ix_published_content_scheduled_at"), table_name="published_content")
    op.drop_column("published_content", "scheduled_at")

    # Postgres cannot drop individual enum values; recreate the type without them.
    op.execute(
        "UPDATE published_content SET status = 'PUBLISHED' "
        "WHERE status IN ('SCHEDULED', 'CANCELLED')"
    )
    op.execute("ALTER TYPE publishstatus RENAME TO publishstatus_old")
    op.execute("CREATE TYPE publishstatus AS ENUM ('PUBLISHED', 'FAILED', 'RETRACTED')")
    op.execute(
        "ALTER TABLE published_content ALTER COLUMN status TYPE publishstatus "
        "USING status::text::publishstatus"
    )
    op.execute("DROP TYPE publishstatus_old")
