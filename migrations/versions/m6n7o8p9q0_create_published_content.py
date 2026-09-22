"""Create published content table

Revision ID: m6n7o8p9q0
Revises: l5m6n7o8p9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m6n7o8p9q0"
down_revision: str | None = "l5m6n7o8p9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

publish_status = postgresql.ENUM(
    "PUBLISHED", "FAILED", "RETRACTED", name="publishstatus", create_type=False
)
publish_method = postgresql.ENUM("MANUAL", "API", name="publishmethod", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    publish_status.create(bind, checkfirst=True)
    publish_method.create(bind, checkfirst=True)

    op.create_table(
        "published_content",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("publish_method", publish_method, nullable=False),
        sa.Column("status", publish_status, nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["draft_id"], ["content_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["content_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    for column in ("draft_id", "profile_id", "platform", "status", "published_at", "created_at"):
        op.create_index(op.f(f"ix_published_content_{column}"), "published_content", [column])


def downgrade() -> None:
    for column in ("created_at", "published_at", "status", "platform", "profile_id", "draft_id"):
        op.drop_index(op.f(f"ix_published_content_{column}"), table_name="published_content")
    op.drop_table("published_content")

    bind = op.get_bind()
    publish_method.drop(bind, checkfirst=True)
    publish_status.drop(bind, checkfirst=True)
