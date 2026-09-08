"""Create content briefs

Revision ID: h1i2j3k4l5m6
Revises: g9h0i1j2k3l4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h1i2j3k4l5m6"
down_revision: str | None = "g9h0i1j2k3l4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

brief_status = postgresql.ENUM("DRAFT", "READY", "APPROVED", "ARCHIVED", name="briefstatus")
generation_source = postgresql.ENUM(
    "MANUAL", "DETERMINISTIC", "AI_ASSISTED", name="generationsource"
)


def upgrade() -> None:
    bind = op.get_bind()
    brief_status.create(bind, checkfirst=True)
    generation_source.create(bind, checkfirst=True)
    op.create_table(
        "content_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("core_message", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text()),
        sa.Column("big_idea", sa.Text()),
        sa.Column("strategic_rationale", sa.Text(), nullable=False),
        sa.Column(
            "target_objective",
            postgresql.ENUM(
                "GROWTH",
                "AUTHORITY",
                "LEAD_GEN",
                "SALES",
                name="targetobjective",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_persona_id", postgresql.UUID(as_uuid=True)),
        sa.Column("target_pain_point_id", postgresql.UUID(as_uuid=True)),
        sa.Column("target_desire_id", postgresql.UUID(as_uuid=True)),
        sa.Column("target_audience_question_id", postgresql.UUID(as_uuid=True)),
        sa.Column("recommended_format", sa.String(length=64)),
        sa.Column(
            "recommended_platform", sa.String(length=32), nullable=False, server_default="other"
        ),
        sa.Column("recommended_length", sa.String(length=128)),
        sa.Column("tone", sa.Text()),
        sa.Column("voice_guidelines", sa.Text()),
        sa.Column("cta_strategy", sa.Text()),
        sa.Column("key_points", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("supporting_context", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("success_criteria", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("brief_version", sa.String(length=16), nullable=False, server_default="v1"),
        sa.Column("generation_source", generation_source, nullable=False),
        sa.Column("status", brief_status, nullable=False, server_default="DRAFT"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["content_opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["target_persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_pain_point_id"], ["pain_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_desire_id"], ["desires.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["target_audience_question_id"], ["audience_questions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "profile_id",
        "opportunity_id",
        "target_persona_id",
        "target_pain_point_id",
        "target_desire_id",
        "target_audience_question_id",
        "recommended_format",
        "recommended_platform",
        "target_objective",
        "generation_source",
        "status",
        "created_at",
    ):
        op.create_index(op.f(f"ix_content_briefs_{column}"), "content_briefs", [column])


def downgrade() -> None:
    for column in (
        "created_at",
        "status",
        "generation_source",
        "target_objective",
        "recommended_platform",
        "recommended_format",
        "target_audience_question_id",
        "target_desire_id",
        "target_pain_point_id",
        "target_persona_id",
        "opportunity_id",
        "profile_id",
    ):
        op.drop_index(op.f(f"ix_content_briefs_{column}"), table_name="content_briefs")
    op.drop_table("content_briefs")
    bind = op.get_bind()
    generation_source.drop(bind, checkfirst=True)
    brief_status.drop(bind, checkfirst=True)
