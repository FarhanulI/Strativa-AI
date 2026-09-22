"""Add content evaluation tables

Revision ID: l5m6n7o8p9
Revises: k4l5m6n7o8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "l5m6n7o8p9"
down_revision: str | None = "k4l5m6n7o8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

evaluation_classification = postgresql.ENUM(
    "EXCELLENT",
    "STRONG",
    "ACCEPTABLE",
    "WEAK",
    "POOR",
    name="evaluationclassification",
    create_type=False,
)
evaluation_dimension = postgresql.ENUM(
    "STRATEGIC_ALIGNMENT",
    "AUDIENCE_RELEVANCE",
    "HOOK_STRENGTH",
    "MESSAGE_CLARITY",
    "NARRATIVE_COHERENCE",
    "FORMAT_ALIGNMENT",
    "EMOTIONAL_ALIGNMENT",
    "CTA_ALIGNMENT",
    "BRAND_ALIGNMENT",
    name="evaluationdimension",
    create_type=False,
)
evaluation_severity = postgresql.ENUM(
    "POSITIVE", "WARNING", "CRITICAL", name="evaluationseverity", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    evaluation_classification.create(bind, checkfirst=True)
    evaluation_dimension.create(bind, checkfirst=True)
    evaluation_severity.create(bind, checkfirst=True)

    op.create_table(
        "content_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("strategic_alignment_score", sa.Float(), nullable=False),
        sa.Column("audience_relevance_score", sa.Float(), nullable=False),
        sa.Column("hook_strength_score", sa.Float(), nullable=False),
        sa.Column("message_clarity_score", sa.Float(), nullable=False),
        sa.Column("narrative_coherence_score", sa.Float(), nullable=False),
        sa.Column("format_alignment_score", sa.Float(), nullable=False),
        sa.Column("emotional_alignment_score", sa.Float(), nullable=False),
        sa.Column("cta_alignment_score", sa.Float(), nullable=False),
        sa.Column("brand_alignment_score", sa.Float(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("classification", evaluation_classification, nullable=False),
        sa.Column("generation_source", sa.String(length=32), nullable=False),
        sa.Column("ai_provider", sa.String(length=64), nullable=True),
        sa.Column("ai_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draft_id"], ["content_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["variation_id"], ["content_draft_variations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for common queries
    for column in ("profile_id", "draft_id", "variation_id", "overall_score", "classification", "created_at"):
        op.create_index(op.f(f"ix_content_evaluations_{column}"), "content_evaluations", [column])

    op.create_table(
        "content_evaluation_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension", evaluation_dimension, nullable=False),
        sa.Column("severity", evaluation_severity, nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["evaluation_id"], ["content_evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for common queries
    for column in ("evaluation_id", "dimension", "severity", "created_at"):
        op.create_index(op.f(f"ix_content_evaluation_findings_{column}"), "content_evaluation_findings", [column])


def downgrade() -> None:
    for column in ("created_at", "severity", "dimension", "evaluation_id"):
        op.drop_index(
            op.f(f"ix_content_evaluation_findings_{column}"), table_name="content_evaluation_findings"
        )
    op.drop_table("content_evaluation_findings")

    for column in ("created_at", "classification", "overall_score", "variation_id", "draft_id", "profile_id"):
        op.drop_index(op.f(f"ix_content_evaluations_{column}"), table_name="content_evaluations")
    op.drop_table("content_evaluations")

    bind = op.get_bind()
    evaluation_severity.drop(bind, checkfirst=True)
    evaluation_dimension.drop(bind, checkfirst=True)
    evaluation_classification.drop(bind, checkfirst=True)
