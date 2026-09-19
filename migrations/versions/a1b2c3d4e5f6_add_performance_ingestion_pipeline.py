"""Add performance ingestion pipeline

Revision ID: a1b2c3d4e5f6
Revises: z9a0b1c2d3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "z9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_performance",
        sa.Column("published_content_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "content_performance",
        sa.Column("reporting_period", sa.Date(), nullable=True),
    )
    op.create_foreign_key(
        "fk_content_performance_published_content_id",
        "content_performance",
        "published_content",
        ["published_content_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_content_performance_published_content_id"),
        "content_performance",
        ["published_content_id"],
    )
    op.create_index(
        "ix_content_performance_profile_published",
        "content_performance",
        ["profile_id", "published_content_id"],
    )
    op.create_unique_constraint(
        "uq_content_performance_published_period",
        "content_performance",
        ["published_content_id", "reporting_period"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_content_performance_published_period", "content_performance", type_="unique"
    )
    op.drop_index("ix_content_performance_profile_published", table_name="content_performance")
    op.drop_index(
        op.f("ix_content_performance_published_content_id"), table_name="content_performance"
    )
    op.drop_constraint(
        "fk_content_performance_published_content_id", "content_performance", type_="foreignkey"
    )
    op.drop_column("content_performance", "reporting_period")
    op.drop_column("content_performance", "published_content_id")
