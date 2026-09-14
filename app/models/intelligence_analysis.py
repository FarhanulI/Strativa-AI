import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.database import Base


class AnalysisGenerationSource(StrEnum):
    AI = "ai"
    AI_FALLBACK = "ai_fallback"
    INSUFFICIENT_DATA = "insufficient_data"


class GroundingBasis(StrEnum):
    """What kind of data a domain analysis was grounded on: onboarding-stated
    profile data with no observed signal history yet (STATED), accumulated
    signal/record data (OBSERVED), or both (MIXED). Only meaningful for a
    `sufficient` grounding result — an `insufficient_data` analysis leaves
    this null, since no basis was actually used to reason.
    """

    STATED = "stated"
    OBSERVED = "observed"
    MIXED = "mixed"


class IntelligenceAnalysisMixin:
    """Shared columns for a domain's stored LLM-reasoning result.

    Brand/Audience/Market analysis are separate tables (one per domain, per
    the day-16 spec) but identical in shape, so the columns live here once.
    `is_current` gives O(1) latest-analysis lookup; `source_fingerprint`
    captures the grounding data's shape (record count + latest timestamp) at
    generation time so a GET can detect a material data change without an
    event hook on every domain CRUD service.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    @declared_attr
    def profile_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
        )

    json_type = JSON().with_variant(JSONB, "postgresql")

    insights: Mapped[list[Any]] = mapped_column(json_type, nullable=False, default=list)
    grounded_on: Mapped[list[Any]] = mapped_column(json_type, nullable=False, default=list)
    source_fingerprint: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    generation_source: Mapped[AnalysisGenerationSource] = mapped_column(
        SqlEnum(AnalysisGenerationSource), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class BrandAnalysis(IntelligenceAnalysisMixin, Base):
    __tablename__ = "brand_analysis"
    __table_args__ = (
        Index("ix_brand_analysis_profile_id_generated_at", "profile_id", "generated_at"),
        Index("ix_brand_analysis_profile_id_is_current", "profile_id", "is_current"),
    )


class AudienceAnalysis(IntelligenceAnalysisMixin, Base):
    __tablename__ = "audience_analysis"
    __table_args__ = (
        Index("ix_audience_analysis_profile_id_generated_at", "profile_id", "generated_at"),
        Index("ix_audience_analysis_profile_id_is_current", "profile_id", "is_current"),
    )

    grounding_basis: Mapped[GroundingBasis | None] = mapped_column(
        SqlEnum(GroundingBasis), nullable=True
    )


class MarketAnalysis(IntelligenceAnalysisMixin, Base):
    __tablename__ = "market_analysis"
    __table_args__ = (
        Index("ix_market_analysis_profile_id_generated_at", "profile_id", "generated_at"),
        Index("ix_market_analysis_profile_id_is_current", "profile_id", "is_current"),
    )

    grounding_basis: Mapped[GroundingBasis | None] = mapped_column(
        SqlEnum(GroundingBasis), nullable=True
    )
