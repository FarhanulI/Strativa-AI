import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class AIJob(Base):
    """Durable status record for a background AI/execution job.

    This table tracks status only — the job's input payload lives in the
    queue message (arq), not here, so a durable row exists even though no
    product feature submits real jobs yet (Day 15 is pure infrastructure;
    Days 17+ register real task_type handlers and call
    `app.infrastructure.jobs.service.submit_job`).
    """

    __tablename__ = "ai_jobs"
    __table_args__ = (
        Index("ix_ai_jobs_profile_id_status", "profile_id", "status"),
        Index("ix_ai_jobs_status_submitted_at", "status", "submitted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        SqlEnum(JobStatus), nullable=False, default=JobStatus.QUEUED, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
