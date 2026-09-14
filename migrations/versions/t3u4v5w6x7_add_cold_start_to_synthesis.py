"""add cold_start to content intelligence synthesis

Revision ID: t3u4v5w6x7
Revises: s2t3u4v5w6
Create Date: 2026-09-14 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "t3u4v5w6x7"
down_revision: str | None = "s2t3u4v5w6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "content_intelligence_synthesis"


def upgrade() -> None:
    # server_default backfills every existing row to false -- rows
    # generated before this distinction existed are never retroactively
    # reclassified as cold_start=true (see docs/development/day-17.md's
    # Cold-Start / Activation Mode section).
    op.add_column(
        TABLE,
        sa.Column("cold_start", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column(TABLE, "cold_start")
