"""Create ai_jobs table for durable background job status tracking

Revision ID: o8p9q0r1s2
Revises: n7o8p9q0r1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o8p9q0r1s2"
down_revision: str | None = "n7o8p9q0r1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

job_status_enum = sa.Enum("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", name="jobstatus")


def upgrade() -> None:
    job_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("content_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", job_status_enum, nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("result_ref", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_ai_jobs_task_type", "ai_jobs", ["task_type"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])
    op.create_index("ix_ai_jobs_profile_id_status", "ai_jobs", ["profile_id", "status"])
    op.create_index("ix_ai_jobs_status_submitted_at", "ai_jobs", ["status", "submitted_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_status_submitted_at", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_profile_id_status", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_status", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_task_type", table_name="ai_jobs")
    op.drop_table("ai_jobs")
    job_status_enum.drop(op.get_bind(), checkfirst=True)
