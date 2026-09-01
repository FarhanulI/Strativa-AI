"""Add audience intelligence domain

Revision ID: c3d4e5f6g7h8
Revises: 78e5a005d8db
Create Date: 2026-08-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "78e5a005d8db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audience_intelligence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("content_profile_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("geography", sa.Text(), nullable=True),
        sa.Column(
            "demographics", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "psychographics", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("behaviors", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "content_preferences",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_profile_id"], ["content_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_profile_id"),
    )
    op.create_index(
        op.f("ix_audience_intelligence_content_profile_id"),
        "audience_intelligence",
        ["content_profile_id"],
        unique=False,
    )

    op.create_table(
        "personas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_intelligence_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("demographics", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "psychographics", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("goals", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "pain_points", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("desires", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("behaviors", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "content_preferences",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audience_intelligence_id"],
            ["audience_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_personas_audience_intelligence_id"),
        "personas",
        ["audience_intelligence_id"],
        unique=False,
    )

    op.create_table(
        "pain_points",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_intelligence_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audience_intelligence_id"],
            ["audience_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pain_points_audience_intelligence_id"),
        "pain_points",
        ["audience_intelligence_id"],
        unique=False,
    )

    op.create_table(
        "desires",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_intelligence_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audience_intelligence_id"],
            ["audience_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_desires_audience_intelligence_id"),
        "desires",
        ["audience_intelligence_id"],
        unique=False,
    )

    op.create_table(
        "audience_questions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_intelligence_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audience_intelligence_id"],
            ["audience_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audience_questions_audience_intelligence_id"),
        "audience_questions",
        ["audience_intelligence_id"],
        unique=False,
    )

    op.create_table(
        "audience_objections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_intelligence_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["audience_intelligence_id"],
            ["audience_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audience_objections_audience_intelligence_id"),
        "audience_objections",
        ["audience_intelligence_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_audience_objections_audience_intelligence_id"),
        table_name="audience_objections",
    )
    op.drop_table("audience_objections")
    op.drop_index(
        op.f("ix_audience_questions_audience_intelligence_id"),
        table_name="audience_questions",
    )
    op.drop_table("audience_questions")
    op.drop_index(op.f("ix_desires_audience_intelligence_id"), table_name="desires")
    op.drop_table("desires")
    op.drop_index(
        op.f("ix_pain_points_audience_intelligence_id"), table_name="pain_points"
    )
    op.drop_table("pain_points")
    op.drop_index(op.f("ix_personas_audience_intelligence_id"), table_name="personas")
    op.drop_table("personas")
    op.drop_index(
        op.f("ix_audience_intelligence_content_profile_id"),
        table_name="audience_intelligence",
    )
    op.drop_table("audience_intelligence")
