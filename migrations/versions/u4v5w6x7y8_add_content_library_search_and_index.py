"""Add content library composite index and full-text search column

Revision ID: u4v5w6x7y8
Revises: t3u4v5w6x7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u4v5w6x7y8"
down_revision: str | None = "t3u4v5w6x7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Supports the default cursor-paginated library view: filter by
    # profile_id/status, ordered by created_at DESC with id as the cursor
    # tie-break for stable ordering.
    op.create_index(
        "ix_content_drafts_profile_status_created_id",
        "content_drafts",
        ["profile_id", "status", sa.text("created_at DESC"), "id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # A generated column (preferred over an application trigger per the
        # Day 19 spec) kept current automatically by Postgres on every
        # insert/update of title/hook/caption.
        op.execute(
            """
            ALTER TABLE content_drafts
            ADD COLUMN search_vector tsvector
            GENERATED ALWAYS AS (
                to_tsvector(
                    'english',
                    coalesce(title, '') || ' ' || coalesce(hook, '') || ' ' || coalesce(caption, '')
                )
            ) STORED
            """
        )
        op.create_index(
            "ix_content_drafts_search_vector",
            "content_drafts",
            ["search_vector"],
            postgresql_using="gin",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_content_drafts_search_vector", table_name="content_drafts")
        op.execute("ALTER TABLE content_drafts DROP COLUMN search_vector")

    op.drop_index("ix_content_drafts_profile_status_created_id", table_name="content_drafts")
