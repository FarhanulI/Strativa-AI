import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_profile import ContentProfile
    from app.models.performance_analysis import PerformanceAnalysis


class PerformanceInsight(Base):
    __tablename__ = "performance_insight"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", name="ck_insight_confidence"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    performance_analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("performance_analysis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insight_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    likely_reason: Mapped[str] = mapped_column(Text, nullable=False)
    strategic_learning: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    json_type = JSON().with_variant(JSONB, "postgresql")
    evidence: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
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

    profile: Mapped["ContentProfile"] = relationship(lazy="selectin")
    analysis: Mapped["PerformanceAnalysis"] = relationship(
        back_populates="insights", lazy="selectin"
    )
