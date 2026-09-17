"""Add foreign key from workspace_members.user_id to users.id

Revision ID: w6x7y8z9a0
Revises: v5w6x7y8z9

Part of Day 21 - Ownership-Chain Enforcement Retrofit. Replaces the bare,
unenforced `user_id String(255)` column with a real UUID foreign key to
`users.id`, so `WorkspaceMember` rows are guaranteed to reference an
existing authenticated user.

Any pre-existing `workspace_members.user_id` value that is not a
well-formed UUID matching a real `users.id` row would fail the `USING
user_id::uuid` cast / FK constraint below rather than being silently
dropped or coerced -- per this day's spec, such a row must be flagged and
fixed manually (there is no automatic remediation here). In this
project's actual data (no signup endpoint yet; only pre-Day-20 test/seed
rows and Day 20's own `seed_user` fixture, which already writes
`str(user.id)`), no such row is expected to exist.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "w6x7y8z9a0"
down_revision: str | None = "v5w6x7y8z9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Fail loudly (rather than silently coercing) if any existing row's
        # user_id isn't a real users.id -- this is exactly the case the
        # day's spec says must be flagged, not auto-fixed.
        op.execute(
            """
            DO $$
            DECLARE
                orphan_count integer;
            BEGIN
                SELECT count(*) INTO orphan_count
                FROM workspace_members wm
                WHERE wm.user_id !~
                    '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                   OR NOT EXISTS (
                       SELECT 1 FROM users u WHERE u.id = wm.user_id::uuid
                   );
                IF orphan_count > 0 THEN
                    RAISE EXCEPTION
                        'workspace_members has % row(s) whose user_id does not '
                        'match an existing users.id -- fix or remove these rows '
                        'before running this migration', orphan_count;
                END IF;
            END $$;
            """
        )
        op.alter_column(
            "workspace_members",
            "user_id",
            type_=sa.UUID(),
            postgresql_using="user_id::uuid",
            existing_nullable=False,
        )
    else:
        # SQLite (test convention): no real pre-existing data to validate;
        # batch mode handles the type change without a USING cast.
        with op.batch_alter_table("workspace_members") as batch_op:
            batch_op.alter_column(
                "user_id",
                type_=sa.UUID(),
                existing_nullable=False,
            )

    op.create_foreign_key(
        "fk_workspace_members_user_id_users",
        "workspace_members",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_workspace_members_user_id_workspace_id",
        "workspace_members",
        ["user_id", "workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_members_user_id_workspace_id", table_name="workspace_members")
    op.drop_constraint(
        "fk_workspace_members_user_id_users", "workspace_members", type_="foreignkey"
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "workspace_members",
            "user_id",
            type_=sa.String(length=255),
            postgresql_using="user_id::text",
            existing_nullable=False,
        )
    else:
        with op.batch_alter_table("workspace_members") as batch_op:
            batch_op.alter_column(
                "user_id",
                type_=sa.String(length=255),
                existing_nullable=False,
            )
