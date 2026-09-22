"""Add learnings

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

learning_dimension = postgresql.ENUM(
    "FORMAT",
    "TOPIC",
    "PILLAR",
    "HOOK_STYLE",
    "CTA",
    "TIMING",
    name="learningdimension",
    create_type=False,
)
learning_status = postgresql.ENUM(
    "ACTIVE", "SUPERSEDED", name="learningstatus", create_type=False
)
explanation_generation_source = postgresql.ENUM(
    "AI", "DETERMINISTIC", name="explanationgenerationsource", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    learning_dimension.create(bind, checkfirst=True)
    learning_status.create(bind, checkfirst=True)
    explanation_generation_source.create(bind, checkfirst=True)

    op.create_table(
        "learnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension", learning_dimension, nullable=False),
        sa.Column("dimension_value", sa.String(length=128), nullable=False),
        sa.Column("pattern_description", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "explanation_generation_source",
            explanation_generation_source,
            nullable=False,
            server_default="DETERMINISTIC",
        ),
        sa.Column("confidence_level", sa.Float(), nullable=False),
        sa.Column(
            "supporting_evidence",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "status", learning_status, nullable=False, server_default="ACTIVE"
        ),
        sa.Column(
            "extraction_version",
            sa.String(length=64),
            nullable=False,
            server_default="learning_extraction_v1",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "confidence_level >= 0 AND confidence_level <= 1", name="ck_learning_confidence"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "dimension",
            "dimension_value",
            name="uq_learning_profile_dimension_value",
        ),
    )
    op.create_index(op.f("ix_learnings_profile_id"), "learnings", ["profile_id"])
    op.create_index(op.f("ix_learnings_status"), "learnings", ["status"])
    op.create_index(
        "ix_learnings_profile_status_dimension", "learnings", ["profile_id", "status", "dimension"]
    )


def downgrade() -> None:
    op.drop_index("ix_learnings_profile_status_dimension", table_name="learnings")
    op.drop_index(op.f("ix_learnings_status"), table_name="learnings")
    op.drop_index(op.f("ix_learnings_profile_id"), table_name="learnings")
    op.drop_table("learnings")

    bind = op.get_bind()
    explanation_generation_source.drop(bind, checkfirst=True)
    learning_status.drop(bind, checkfirst=True)
    learning_dimension.drop(bind, checkfirst=True)
