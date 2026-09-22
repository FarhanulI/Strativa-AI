"""Add brand/audience/market intelligence analysis tables

Revision ID: p9q0r1s2t3
Revises: o8p9q0r1s2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p9q0r1s2t3"
down_revision: str | None = "o8p9q0r1s2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

generation_source_enum = postgresql.ENUM(
    "AI", "AI_FALLBACK", "INSUFFICIENT_DATA", name="analysisgenerationsource", create_type=False
)

TABLES = ("brand_analysis", "audience_analysis", "market_analysis")


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    bind = op.get_bind()
    generation_source_enum.create(bind, checkfirst=True)

    for table in TABLES:
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("insights", json_type, nullable=False),
            sa.Column("grounded_on", json_type, nullable=False),
            sa.Column("source_fingerprint", json_type),
            sa.Column(
                "generation_source",
                generation_source_enum,
                nullable=False,
            ),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("analysis_version", sa.String(64), nullable=False),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        )
        op.create_index(op.f(f"ix_{table}_profile_id"), table, ["profile_id"])
        op.create_index(op.f(f"ix_{table}_is_current"), table, ["is_current"])
        op.create_index(
            f"ix_{table}_profile_id_generated_at", table, ["profile_id", "generated_at"]
        )
        op.create_index(f"ix_{table}_profile_id_is_current", table, ["profile_id", "is_current"])


def downgrade() -> None:
    for table in TABLES:
        for index in list(op.get_bind().dialect.get_indexes(table)):
            op.drop_index(index["name"], table_name=table)
        op.drop_table(table)
    generation_source_enum.drop(op.get_bind(), checkfirst=True)
