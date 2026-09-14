"""add opportunity rationale reasoning columns

Revision ID: r1s2t3u4v5
Revises: q0r1s2t3u4
Create Date: 2026-09-14 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r1s2t3u4v5"
down_revision: str | None = "q0r1s2t3u4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "content_opportunities"

# Score, score components, priority, and ranking are untouched by this
# migration (see docs/development/day-18.md "HARD BOUNDARY") -- only the
# provenance of strategic_rationale's text gains two new columns.
rationale_generation_source_enum = postgresql.ENUM(
    "AI", "DETERMINISTIC", name="rationalegenerationsource"
)


def upgrade() -> None:
    bind = op.get_bind()
    rationale_generation_source_enum.create(bind, checkfirst=True)

    op.add_column(
        TABLE,
        sa.Column(
            "rationale_generation_source",
            rationale_generation_source_enum,
            nullable=False,
            server_default="DETERMINISTIC",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column("rationale_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f(f"ix_{TABLE}_rationale_generation_source"),
        TABLE,
        ["rationale_generation_source"],
    )


def downgrade() -> None:
    op.drop_index(op.f(f"ix_{TABLE}_rationale_generation_source"), table_name=TABLE)
    op.drop_column(TABLE, "rationale_generated_at")
    op.drop_column(TABLE, "rationale_generation_source")

    bind = op.get_bind()
    rationale_generation_source_enum.drop(bind, checkfirst=True)
