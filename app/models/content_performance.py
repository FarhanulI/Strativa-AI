import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_profile import ContentProfile
    from app.models.performance_analysis import PerformanceAnalysis


class ContentPerformance(Base):
    __tablename__ = "content_performance"
    __table_args__ = (
        CheckConstraint(
            "views >= 0 AND reach >= 0 AND impressions >= 0", name="ck_performance_counts_1"
        ),
        CheckConstraint(
            "likes >= 0 AND comments >= 0 AND shares >= 0 AND saves >= 0",
            name="ck_performance_counts_2",
        ),
        CheckConstraint(
            "clicks >= 0 AND conversions >= 0 AND watch_time_seconds >= 0",
            name="ck_performance_counts_3",
        ),
        CheckConstraint(
            "average_watch_time_seconds >= 0", name="ck_performance_average_watch_time"
        ),
        CheckConstraint(
            "completion_rate >= 0 AND completion_rate <= 1", name="ck_performance_completion_rate"
        ),
        CheckConstraint(
            "retention_rate >= 0 AND retention_rate <= 1", name="ck_performance_retention_rate"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    format: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conversions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_watch_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    retention_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    json_type = JSON().with_variant(JSONB, "postgresql")
    performance_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    profile: Mapped["ContentProfile"] = relationship(
        back_populates="performance_records", lazy="selectin"
    )
    analysis: Mapped["PerformanceAnalysis | None"] = relationship(
        back_populates="content_performance",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
