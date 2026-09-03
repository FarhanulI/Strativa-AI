"""Add audience signals and audience opportunity references

Revision ID: f8a9b0c1d2e3
Revises: d5f7a1c2b3e4
Create Date: 2026-09-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8a9b0c1d2e3"
down_revision: tuple[str, str] = ("a1b2c3d4e5f6", "e7f8a9b0c1d2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    audience_signal_type = postgresql.ENUM("QUESTION", name="audiencesignaltype", create_type=False)
    audience_signal_intent = postgresql.ENUM(
        "LEARN",
        "COMPARE",
        "SOLVE",
        "DISCOVER",
        "VALIDATE",
        "ENTERTAIN",
        name="audiencesignalintent",
        create_type=False,
    )
    audience_signal_status = postgresql.ENUM(
        "ACTIVE", "RESOLVED", "EXPIRED", "ARCHIVED", name="audiencesignalstatus", create_type=False
    )
    audience_signal_source = postgresql.ENUM(
        "MANUAL", name="audiencesignalsource", create_type=False
    )
    for enum in (
        audience_signal_type,
        audience_signal_intent,
        audience_signal_status,
        audience_signal_source,
    ):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audience_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", audience_signal_type, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("intent", audience_signal_intent, nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False),
        sa.Column("status", audience_signal_status, nullable=False),
        sa.Column("source", audience_signal_source, nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "strength_score >= 0 AND strength_score <= 1",
            name="ck_audience_signal_strength_score",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "profile_id",
        "signal_type",
        "intent",
        "status",
        "source",
        "strength_score",
        "observed_at",
    ):
        op.create_index(
            op.f(f"ix_audience_signals_{column}"), "audience_signals", [column], unique=False
        )

    op.add_column(
        "content_opportunities",
        sa.Column("audience_signal_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_content_opportunities_audience_signal_id"),
        "content_opportunities",
        ["audience_signal_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_content_opportunities_audience_signal_id",
        "content_opportunities",
        "audience_signals",
        ["audience_signal_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_content_opportunities_audience_signal_id", "content_opportunities", type_="foreignkey"
    )
    op.drop_index(
        op.f("ix_content_opportunities_audience_signal_id"), table_name="content_opportunities"
    )
    op.drop_column("content_opportunities", "audience_signal_id")
    for column in (
        "observed_at",
        "strength_score",
        "source",
        "status",
        "intent",
        "signal_type",
        "profile_id",
    ):
        op.drop_index(op.f(f"ix_audience_signals_{column}"), table_name="audience_signals")
    op.drop_table("audience_signals")
    for enum_name in (
        "audiencesignalsource",
        "audiencesignalstatus",
        "audiencesignalintent",
        "audiencesignaltype",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
