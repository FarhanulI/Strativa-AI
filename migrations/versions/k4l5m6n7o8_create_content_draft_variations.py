"""Create content draft variations

Revision ID: k4l5m6n7o8
Revises: i2j3k4l5m6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "k4l5m6n7o8"
down_revision: str | None = "i2j3k4l5m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

variation_type = postgresql.ENUM(
    "HOOK", "CAPTION", name="variationtype", create_type=False
)
variation_generation_source = postgresql.ENUM(
    "DETERMINISTIC", "AI", name="variationgenerationsource", create_type=False
)


def upgrade() -> None:
    op.add_column("content_drafts", sa.Column("caption", sa.Text(), nullable=True))

    bind = op.get_bind()
    variation_type.create(bind, checkfirst=True)
    variation_generation_source.create(bind, checkfirst=True)
    op.create_table(
        "content_draft_variations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variation_type", variation_type, nullable=False),
        sa.Column("variation_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("generation_source", variation_generation_source, nullable=False),
        sa.Column("ai_provider", sa.String(length=64)),
        sa.Column("ai_model", sa.String(length=128)),
        sa.Column("prompt_version", sa.String(length=64)),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["draft_id"], ["content_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id",
            "variation_type",
            "variation_index",
            name="uq_content_draft_variations_draft_type_index",
        ),
        sa.CheckConstraint(
            "variation_index >= 1", name="ck_content_draft_variations_index_positive"
        ),
    )
    for column in ("draft_id", "variation_type", "generation_source", "created_at"):
        op.create_index(
            op.f(f"ix_content_draft_variations_{column}"), "content_draft_variations", [column]
        )
    op.create_index(
        "uq_content_draft_variations_selected",
        "content_draft_variations",
        ["draft_id", "variation_type"],
        unique=True,
        postgresql_where=sa.text("is_selected = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_content_draft_variations_selected", table_name="content_draft_variations")
    for column in ("created_at", "generation_source", "variation_type", "draft_id"):
        op.drop_index(
            op.f(f"ix_content_draft_variations_{column}"), table_name="content_draft_variations"
        )
    op.drop_table("content_draft_variations")
    bind = op.get_bind()
    variation_generation_source.drop(bind, checkfirst=True)
    variation_type.drop(bind, checkfirst=True)

    op.drop_column("content_drafts", "caption")
