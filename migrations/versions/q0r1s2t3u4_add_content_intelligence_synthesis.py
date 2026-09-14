"""add content intelligence synthesis

Revision ID: q0r1s2t3u4
Revises: p9q0r1s2t3
Create Date: 2026-09-14 14:10:42.430617

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "q0r1s2t3u4"
down_revision: str | None = "p9q0r1s2t3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "content_intelligence_synthesis"

# Reuses the `analysisgenerationsource` enum type created by p9q0r1s2t3 for
# Brand/Audience/Market analysis (ai | ai_fallback | insufficient_data) --
# synthesis shares the same generation-source vocabulary, so no new
# database enum type is created here (`create_type=False`).
generation_source_enum = postgresql.ENUM(
    "AI", "AI_FALLBACK", "INSUFFICIENT_DATA", name="analysisgenerationsource", create_type=False
)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_themes", json_type, nullable=False),
        sa.Column("supporting_analyses", json_type, nullable=False),
        sa.Column("generation_source", generation_source_enum, nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "synthesis_version",
            sa.String(64),
            nullable=False,
            server_default="strategic_synthesis_v1",
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f(f"ix_{TABLE}_profile_id"), TABLE, ["profile_id"])
    op.create_index(op.f(f"ix_{TABLE}_is_current"), TABLE, ["is_current"])
    op.create_index(op.f(f"ix_{TABLE}_is_stale"), TABLE, ["is_stale"])
    op.create_index(f"ix_{TABLE}_profile_id_generated_at", TABLE, ["profile_id", "generated_at"])
    op.create_index(f"ix_{TABLE}_profile_id_is_current", TABLE, ["profile_id", "is_current"])
    op.create_index(
        f"uq_{TABLE}_current",
        TABLE,
        ["profile_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    for index in list(op.get_bind().dialect.get_indexes(TABLE)):
        op.drop_index(index["name"], table_name=TABLE)
    op.drop_table(TABLE)
