import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_performance import ContentPerformance
    from app.models.content_profile import ContentProfile
    from app.models.performance_insight import PerformanceInsight


class PerformanceClassification(StrEnum):
    EXCEPTIONAL = "exceptional"
    STRONG = "strong"
    NORMAL = "normal"
    WEAK = "weak"
    POOR = "poor"


class PerformanceAnalysis(Base):
    __tablename__ = "performance_analysis"
    __table_args__ = ()

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_performance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_performance.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    share_rate: Mapped[float | None] = mapped_column(Float)
    save_rate: Mapped[float | None] = mapped_column(Float)
    comment_rate: Mapped[float | None] = mapped_column(Float)
    click_through_rate: Mapped[float | None] = mapped_column(Float)
    conversion_rate: Mapped[float | None] = mapped_column(Float)
    baseline_engagement_rate: Mapped[float | None] = mapped_column(Float)
    baseline_share_rate: Mapped[float | None] = mapped_column(Float)
    baseline_save_rate: Mapped[float | None] = mapped_column(Float)
    baseline_retention_rate: Mapped[float | None] = mapped_column(Float)
    relative_engagement: Mapped[float | None] = mapped_column(Float)
    relative_shares: Mapped[float | None] = mapped_column(Float)
    relative_saves: Mapped[float | None] = mapped_column(Float)
    relative_retention: Mapped[float | None] = mapped_column(Float)
    performance_classification: Mapped[str | None] = mapped_column(String(32), index=True)
    baseline_available: Mapped[bool] = mapped_column(default=False, nullable=False)
    comparables_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    json_type = JSON().with_variant(JSONB, "postgresql")
    evidence: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    analysis_version: Mapped[str] = mapped_column(
        String(64), default="performance_analysis_v1", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    profile: Mapped["ContentProfile"] = relationship(lazy="selectin")
    content_performance: Mapped["ContentPerformance"] = relationship(
        back_populates="analysis", lazy="selectin"
    )
    insights: Mapped[list["PerformanceInsight"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", lazy="selectin"
    )
