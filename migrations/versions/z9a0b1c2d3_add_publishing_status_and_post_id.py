"""Add publishing status and platform_post_id to published content

Revision ID: z9a0b1c2d3
Revises: y8z9a0b1c2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z9a0b1c2d3"
down_revision: str | None = "y8z9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New transient claim-then-call state (Day 24): the atomic
    # scheduled->publishing UPDATE is the whole double-claim guarantee: only
    # one instance's UPDATE can match a given SCHEDULED row. published_at is
    # set only once the adapter call actually succeeds.
    op.execute("ALTER TYPE publishstatus ADD VALUE IF NOT EXISTS 'PUBLISHING'")

    op.add_column(
        "published_content",
        sa.Column("platform_post_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("published_content", "platform_post_id")

    # Postgres cannot drop individual enum values; recreate the type without
    # PUBLISHING. Any row still claimed-but-not-finished is treated as failed
    # -- a stuck row is exactly what the Day 24 recovery sweep would have
    # done with it anyway.
    op.execute("UPDATE published_content SET status = 'FAILED' WHERE status = 'PUBLISHING'")
    op.execute("ALTER TYPE publishstatus RENAME TO publishstatus_old")
    op.execute(
        "CREATE TYPE publishstatus AS ENUM "
        "('SCHEDULED', 'PUBLISHED', 'FAILED', 'RETRACTED', 'CANCELLED')"
    )
    op.execute(
        "ALTER TABLE published_content ALTER COLUMN status TYPE publishstatus "
        "USING status::text::publishstatus"
    )
    op.execute("DROP TYPE publishstatus_old")
