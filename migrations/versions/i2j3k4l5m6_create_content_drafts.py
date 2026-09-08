"""Create content drafts

Revision ID: i2j3k4l5m6
Revises: h1i2j3k4l5m6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i2j3k4l5m6"
down_revision: str | None = "h1i2j3k4l5m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

draft_status = postgresql.ENUM("DRAFT", "READY", "APPROVED", "ARCHIVED", name="draftstatus")
draft_generation_source = postgresql.ENUM(
    "DETERMINISTIC", "AI", "AI_FALLBACK", "MANUAL", name="draftgenerationsource"
)
composition_mode = postgresql.ENUM("COMPOSE", "MANUAL", name="compositionmode")


def upgrade() -> None:
    bind = op.get_bind()
    draft_status.create(bind, checkfirst=True)
    draft_generation_source.create(bind, checkfirst=True)
    composition_mode.create(bind, checkfirst=True)
    op.create_table(
        "content_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text()),
        sa.Column("status", draft_status, nullable=False, server_default="DRAFT"),
        sa.Column("generation_source", draft_generation_source, nullable=False),
        sa.Column("composition_mode", composition_mode, nullable=False, server_default="COMPOSE"),
        sa.Column("ai_provider", sa.String(length=64)),
        sa.Column("ai_model", sa.String(length=128)),
        sa.Column("prompt_version", sa.String(length=64)),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brief_id"], ["content_briefs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "profile_id",
        "brief_id",
        "status",
        "platform",
        "format",
        "created_at",
    ):
        op.create_index(op.f(f"ix_content_drafts_{column}"), "content_drafts", [column])


def downgrade() -> None:
    for column in ("created_at", "format", "platform", "status", "brief_id", "profile_id"):
        op.drop_index(op.f(f"ix_content_drafts_{column}"), table_name="content_drafts")
    op.drop_table("content_drafts")
    bind = op.get_bind()
    composition_mode.drop(bind, checkfirst=True)
    draft_generation_source.drop(bind, checkfirst=True)
    draft_status.drop(bind, checkfirst=True)
