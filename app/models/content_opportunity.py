import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.audience_signal import AudienceSignal
    from app.models.content_brief import ContentBrief
    from app.models.content_profile import ContentProfile
    from app.models.market_signal import MarketSignal
    from app.models.performance_insight import PerformanceInsight


class OpportunitySource(StrEnum):
    TREND = "trend"
    PERFORMANCE_GAP = "performance_gap"
    AUDIENCE_QUESTION = "audience_question"
    PILLAR_ROTATION = "pillar_rotation"
    MARKET_CONVERSATION = "market_conversation"


class TargetObjective(StrEnum):
    GROWTH = "growth"
    AUTHORITY = "authority"
    LEAD_GEN = "lead_gen"
    SALES = "sales"


class OpportunityPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OpportunityStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RationaleGenerationSource(StrEnum):
    """Provenance of `ContentOpportunity.strategic_rationale`.

    Unlike score/priority (always deterministic), the rationale text itself
    may come from the `opportunity_reasoning` AI task (see
    docs/development/day-18.md). `DETERMINISTIC` covers both the templated
    placeholder written at creation and the fallback when no current
    synthesis exists yet or the AI provider fails -- there is deliberately
    no separate `ai_fallback` value, because in both fallback cases the
    persisted text is the same deterministic template, not a degraded AI
    output.
    """

    AI = "ai"
    DETERMINISTIC = "deterministic"


class ContentOpportunity(Base):
    __tablename__ = "content_opportunities"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1", name="ck_opportunity_relevance_score"
        ),
        CheckConstraint(
            "opportunity_score >= 0 AND opportunity_score <= 1", name="ck_opportunity_score"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("market_signals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    audience_signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audience_signals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    performance_insight_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("performance_insight.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_signal: Mapped[OpportunitySource] = mapped_column(
        SqlEnum(OpportunitySource), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    strategic_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    target_objective: Mapped[TargetObjective] = mapped_column(
        SqlEnum(TargetObjective), nullable=False, index=True
    )
    recommended_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, index=True, default=0.5)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    priority: Mapped[OpportunityPriority] = mapped_column(
        SqlEnum(OpportunityPriority), nullable=False, index=True
    )
    status: Mapped[OpportunityStatus] = mapped_column(
        SqlEnum(OpportunityStatus), nullable=False, default=OpportunityStatus.DRAFT, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rationale_generation_source: Mapped[RationaleGenerationSource] = mapped_column(
        SqlEnum(RationaleGenerationSource),
        nullable=False,
        default=RationaleGenerationSource.DETERMINISTIC,
        index=True,
    )
    rationale_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    json_type = JSON().with_variant(JSONB, "postgresql")
    opportunity_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
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

    profile: Mapped["ContentProfile"] = relationship(
        back_populates="opportunities", lazy="selectin"
    )
    market_signal: Mapped["MarketSignal | None"] = relationship(
        back_populates="opportunities", lazy="selectin"
    )
    audience_signal: Mapped["AudienceSignal | None"] = relationship(
        back_populates="opportunities", lazy="selectin"
    )
    performance_insight: Mapped["PerformanceInsight | None"] = relationship(lazy="selectin")
    briefs: Mapped[list["ContentBrief"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan", lazy="selectin"
    )
