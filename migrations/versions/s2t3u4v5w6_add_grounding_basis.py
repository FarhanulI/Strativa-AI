"""add grounding_basis to audience/market analysis

Revision ID: s2t3u4v5w6
Revises: r1s2t3u4v5
Create Date: 2026-09-14 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s2t3u4v5w6"
down_revision: str | None = "r1s2t3u4v5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("audience_analysis", "market_analysis")

# stated | observed | mixed -- what kind of data a domain analysis was
# grounded on. Only Audience/Market carry this: Brand's grounding data is
# already always profile-stated, so the distinction doesn't apply there.
grounding_basis_enum = postgresql.ENUM("STATED", "OBSERVED", "MIXED", name="groundingbasis")


def upgrade() -> None:
    bind = op.get_bind()
    grounding_basis_enum.create(bind, checkfirst=True)

    for table in TABLES:
        op.add_column(
            table,
            sa.Column("grounding_basis", grounding_basis_enum, nullable=True),
        )

    # Backfill: every row that predates this column was generated back when
    # `sufficient` could only be reached via accumulated signal/record data
    # (personas+pain points, or topics+market signals) -- the stated-data
    # grounding path this migration's code change adds did not exist yet.
    # So any pre-existing row with real reasoning behind it is `observed`;
    # an `insufficient_data` row has no grounding basis at all and is left
    # NULL.
    for table in TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET grounding_basis = 'OBSERVED' "
                "WHERE generation_source IN ('AI', 'AI_FALLBACK')"
            )
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "grounding_basis")

    bind = op.get_bind()
    grounding_basis_enum.drop(bind, checkfirst=True)
