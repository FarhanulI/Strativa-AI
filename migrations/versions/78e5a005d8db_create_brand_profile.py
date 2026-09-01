"""create brand profile

Revision ID: 78e5a005d8db
Revises: 0002_workspace_business
Create Date: 2026-08-26 01:13:23.735974

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "78e5a005d8db"
down_revision: str | None = "0002_workspace_business"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("mission", sa.Text(), nullable=True),
        sa.Column("vision", sa.Text(), nullable=True),
        sa.Column("unique_selling_proposition", sa.Text(), nullable=True),
        sa.Column("values", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("personality", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("voice", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("tone", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("messaging_guidelines", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("visual_identity", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id"),
    )
    op.create_index(op.f("ix_brands_business_id"), "brands", ["business_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_brands_business_id"), table_name="brands")
    op.drop_table("brands")
