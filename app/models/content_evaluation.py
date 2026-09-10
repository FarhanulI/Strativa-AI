import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_draft import ContentDraft
    from app.models.content_draft_variation import ContentDraftVariation
    from app.models.content_profile import ContentProfile


class EvaluationDimension(StrEnum):
    """Evaluation assessment dimensions."""

    STRATEGIC_ALIGNMENT = "strategic_alignment"
    AUDIENCE_RELEVANCE = "audience_relevance"
    HOOK_STRENGTH = "hook_strength"
    MESSAGE_CLARITY = "message_clarity"
    NARRATIVE_COHERENCE = "narrative_coherence"
    FORMAT_ALIGNMENT = "format_alignment"
    EMOTIONAL_ALIGNMENT = "emotional_alignment"
    CTA_ALIGNMENT = "cta_alignment"
    BRAND_ALIGNMENT = "brand_alignment"


class EvaluationSeverity(StrEnum):
    """Finding severity levels."""

    POSITIVE = "positive"
    WARNING = "warning"
    CRITICAL = "critical"


class EvaluationClassification(StrEnum):
    """Overall evaluation classification based on overall_score."""

    EXCELLENT = "excellent"  # >= 0.85
    STRONG = "strong"  # >= 0.70
    ACCEPTABLE = "acceptable"  # >= 0.55
    WEAK = "weak"  # >= 0.40
    POOR = "poor"  # < 0.40


class ContentEvaluation(Base):
    """
    Evaluation of a content draft against its strategic brief.

    Each evaluation represents an assessment at a point in time.
    Multiple evaluations can exist for the same draft (historical trail).
    """

    __tablename__ = "content_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_draft_variations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Dimension scores (0.0 to 1.0)
    strategic_alignment_score: Mapped[float] = mapped_column(nullable=False)
    audience_relevance_score: Mapped[float] = mapped_column(nullable=False)
    hook_strength_score: Mapped[float] = mapped_column(nullable=False)
    message_clarity_score: Mapped[float] = mapped_column(nullable=False)
    narrative_coherence_score: Mapped[float] = mapped_column(nullable=False)
    format_alignment_score: Mapped[float] = mapped_column(nullable=False)
    emotional_alignment_score: Mapped[float] = mapped_column(nullable=False)
    cta_alignment_score: Mapped[float] = mapped_column(nullable=False)
    brand_alignment_score: Mapped[float] = mapped_column(nullable=False)

    # Overall score and classification
    overall_score: Mapped[float] = mapped_column(nullable=False, index=True)
    classification: Mapped[EvaluationClassification] = mapped_column(
        SqlEnum(EvaluationClassification), nullable=False, index=True
    )

    # Generation metadata
    generation_source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ai_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    evaluation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
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

    # Relationships
    profile: Mapped["ContentProfile"] = relationship(lazy="selectin")
    draft: Mapped["ContentDraft"] = relationship(lazy="selectin")
    variation: Mapped["ContentDraftVariation | None"] = relationship(lazy="selectin")
    findings: Mapped[list["ContentEvaluationFinding"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan", lazy="selectin"
    )
