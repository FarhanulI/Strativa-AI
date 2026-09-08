"""Add performance intelligence

Revision ID: g9h0i1j2k3l4
Revises: f8a9b0c1d2e3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g9h0i1j2k3l4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "content_performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True)),
        sa.Column("external_post_id", sa.String(255)),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(64)),
        sa.Column("topic", sa.Text()),
        sa.Column("format", sa.String(64)),
        sa.Column("hook", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *[
            sa.Column(name, sa.Integer())
            for name in (
                "views",
                "reach",
                "impressions",
                "likes",
                "comments",
                "shares",
                "saves",
                "clicks",
                "conversions",
            )
        ],
        sa.Column("watch_time_seconds", sa.Float()),
        sa.Column("average_watch_time_seconds", sa.Float()),
        sa.Column("completion_rate", sa.Float()),
        sa.Column("retention_rate", sa.Float()),
        sa.Column("metadata", json_type),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "views >= 0 AND reach >= 0 AND impressions >= 0", name="ck_performance_counts_1"
        ),
        sa.CheckConstraint(
            "completion_rate >= 0 AND completion_rate <= 1", name="ck_performance_completion_rate"
        ),
        sa.CheckConstraint(
            "retention_rate >= 0 AND retention_rate <= 1", name="ck_performance_retention_rate"
        ),
    )
    for column in (
        "profile_id",
        "platform",
        "external_post_id",
        "topic",
        "format",
        "published_at",
        "created_at",
    ):
        op.create_index(op.f(f"ix_content_performance_{column}"), "content_performance", [column])
    op.create_table(
        "performance_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "content_performance_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True
        ),
        *[
            sa.Column(name, sa.Float())
            for name in (
                "engagement_rate",
                "share_rate",
                "save_rate",
                "comment_rate",
                "click_through_rate",
                "conversion_rate",
                "baseline_engagement_rate",
                "baseline_share_rate",
                "baseline_save_rate",
                "baseline_retention_rate",
                "relative_engagement",
                "relative_shares",
                "relative_saves",
                "relative_retention",
            )
        ],
        sa.Column("performance_classification", sa.String(32)),
        sa.Column("baseline_available", sa.Boolean(), nullable=False),
        sa.Column("comparables_count", sa.Integer(), nullable=False),
        sa.Column("evidence", json_type),
        sa.Column("analysis_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_performance_id"], ["content_performance.id"], ondelete="CASCADE"
        ),
    )
    for column in (
        "profile_id",
        "content_performance_id",
        "performance_classification",
        "created_at",
    ):
        op.create_index(op.f(f"ix_performance_analysis_{column}"), "performance_analysis", [column])
    op.create_table(
        "performance_insight",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performance_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("insight_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("likely_reason", sa.Text(), nullable=False),
        sa.Column("strategic_learning", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("evidence", json_type),
        sa.Column("model_provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["performance_analysis_id"], ["performance_analysis.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", name="ck_insight_confidence"
        ),
    )
    for column in (
        "profile_id",
        "performance_analysis_id",
        "insight_type",
        "confidence_score",
        "status",
        "created_at",
    ):
        op.create_index(op.f(f"ix_performance_insight_{column}"), "performance_insight", [column])
    op.add_column(
        "content_opportunities", sa.Column("performance_insight_id", postgresql.UUID(as_uuid=True))
    )
    op.create_foreign_key(
        "fk_opportunity_performance_insight",
        "content_opportunities",
        "performance_insight",
        ["performance_insight_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_content_opportunities_performance_insight_id"),
        "content_opportunities",
        ["performance_insight_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_content_opportunities_performance_insight_id"), table_name="content_opportunities"
    )
    op.drop_constraint(
        "fk_opportunity_performance_insight", "content_opportunities", type_="foreignkey"
    )
    op.drop_column("content_opportunities", "performance_insight_id")
    for table in ("performance_insight", "performance_analysis", "content_performance"):
        for index in list(op.get_bind().dialect.get_indexes(table)):
            op.drop_index(index["name"], table_name=table)
        op.drop_table(table)
