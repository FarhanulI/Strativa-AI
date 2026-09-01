"""Add market intelligence domain

Revision ID: d5f7a1c2b3e4
Revises: c3d4e5f6g7h8
Create Date: 2026-09-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5f7a1c2b3e4"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_intelligence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("market_context", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_profile_id"], ["content_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_profile_id"),
    )
    op.create_index(
        op.f("ix_market_intelligence_content_profile_id"),
        "market_intelligence",
        ["content_profile_id"],
        unique=False,
    )

    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_intelligence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["market_intelligence_id"],
            ["market_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_intelligence_id",
            "name",
            name="uq_topics_market_intelligence_id_name",
        ),
    )
    op.create_index(
        op.f("ix_topics_market_intelligence_id"),
        "topics",
        ["market_intelligence_id"],
        unique=False,
    )

    op.create_table(
        "market_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_intelligence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("signal_type", sa.String(length=64), nullable=True),
        sa.Column("velocity_score", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("engagement_score", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["market_intelligence_id"],
            ["market_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_signals_market_intelligence_id"),
        "market_signals",
        ["market_intelligence_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_signals_topic_id"),
        "market_signals",
        ["topic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_signals_status"),
        "market_signals",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_signals_signal_type"),
        "market_signals",
        ["signal_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_signals_source_type"),
        "market_signals",
        ["source_type"],
        unique=False,
    )

    op.create_table(
        "competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_intelligence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("profile_url", sa.Text(), nullable=True),
        sa.Column("niche", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["market_intelligence_id"],
            ["market_intelligence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        # NULL profile_url values are treated as distinct in Postgres, so
        # multiple competitors without a profile URL remain allowed.
        sa.UniqueConstraint(
            "market_intelligence_id",
            "platform",
            "profile_url",
            name="uq_competitors_market_platform_url",
        ),
    )
    op.create_index(
        op.f("ix_competitors_market_intelligence_id"),
        "competitors",
        ["market_intelligence_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_competitors_market_intelligence_id"), table_name="competitors")
    op.drop_table("competitors")

    op.drop_index(op.f("ix_market_signals_source_type"), table_name="market_signals")
    op.drop_index(op.f("ix_market_signals_signal_type"), table_name="market_signals")
    op.drop_index(op.f("ix_market_signals_status"), table_name="market_signals")
    op.drop_index(op.f("ix_market_signals_topic_id"), table_name="market_signals")
    op.drop_index(op.f("ix_market_signals_market_intelligence_id"), table_name="market_signals")
    op.drop_table("market_signals")

    op.drop_index(op.f("ix_topics_market_intelligence_id"), table_name="topics")
    op.drop_table("topics")

    op.drop_index(
        op.f("ix_market_intelligence_content_profile_id"),
        table_name="market_intelligence",
    )
    op.drop_table("market_intelligence")
