"""Add Workspace.onboarding_status and ContentProfile.primary_niche/platforms

Revision ID: x7y8z9a0b1
Revises: w6x7y8z9a0

Part of Day 22 - Registration & Onboarding. `onboarding_status` lives on
`Workspace` (not `ContentProfile`) because it must be checkable before any
profile exists. `primary_niche` and `platforms` are additive
`ContentProfile` columns: neither concept has an existing home in the
Day 2/3/16 schema (topics/expertise/goals don't fit), so this is a
deliberate, minimal deviation from reusing an existing field.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "x7y8z9a0b1"
down_revision: str | None = "w6x7y8z9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ONBOARDING_STATUS_VALUES = ("not_started", "in_progress", "completed")


def upgrade() -> None:
    onboarding_status_enum = sa.Enum(*_ONBOARDING_STATUS_VALUES, name="workspaceonboardingstatus")
    onboarding_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "workspaces",
        sa.Column(
            "onboarding_status",
            onboarding_status_enum,
            nullable=False,
            server_default="not_started",
        ),
    )

    json_type = sa.JSON().with_variant(JSONB, "postgresql")
    op.add_column(
        "content_profiles",
        sa.Column("primary_niche", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "content_profiles",
        sa.Column("platforms", json_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_profiles", "platforms")
    op.drop_column("content_profiles", "primary_niche")

    op.drop_column("workspaces", "onboarding_status")
    sa.Enum(name="workspaceonboardingstatus").drop(op.get_bind(), checkfirst=True)
