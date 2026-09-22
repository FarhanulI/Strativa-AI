"""Create content opportunities

Revision ID: e7f8a9b0c1d2
Revises: d5f7a1c2b3e4
Create Date: 2026-09-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d5f7a1c2b3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


opportunity_source = postgresql.ENUM(
    "TREND",
    "PERFORMANCE_GAP",
    "AUDIENCE_QUESTION",
    "PILLAR_ROTATION",
    "MARKET_CONVERSATION",
    name="opportunitysource",
    create_type=False,
)
target_objective = postgresql.ENUM(
    "GROWTH", "AUTHORITY", "LEAD_GEN", "SALES", name="targetobjective", create_type=False
)
opportunity_priority = postgresql.ENUM(
    "HIGH", "MEDIUM", "LOW", name="opportunitypriority", create_type=False
)
opportunity_status = postgresql.ENUM(
    "DRAFT", "ACTIVE", "ACCEPTED", "REJECTED", "EXPIRED", name="opportunitystatus", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (opportunity_source, target_objective, opportunity_priority, opportunity_status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "content_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_signal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_signal", opportunity_source, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("strategic_rationale", sa.Text(), nullable=False),
        sa.Column("target_objective", target_objective, nullable=False),
        sa.Column("recommended_format", sa.String(length=64), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("priority", opportunity_priority, nullable=False),
        sa.Column("status", opportunity_status, nullable=False, server_default="DRAFT"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1", name="ck_opportunity_relevance_score"
        ),
        sa.CheckConstraint(
            "opportunity_score >= 0 AND opportunity_score <= 1", name="ck_opportunity_score"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["market_signal_id"], ["market_signals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "profile_id",
        "market_signal_id",
        "source_signal",
        "target_objective",
        "priority",
        "status",
        "opportunity_score",
    ):
        op.create_index(
            op.f(f"ix_content_opportunities_{column}"),
            "content_opportunities",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "opportunity_score",
        "status",
        "priority",
        "target_objective",
        "source_signal",
        "market_signal_id",
        "profile_id",
    ):
        op.drop_index(
            op.f(f"ix_content_opportunities_{column}"), table_name="content_opportunities"
        )
    op.drop_table("content_opportunities")
    bind = op.get_bind()
    for enum in (opportunity_status, opportunity_priority, target_objective, opportunity_source):
        enum.drop(bind, checkfirst=True)
