import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_profile import ContentProfile


class LearningDimension(StrEnum):
    FORMAT = "format"
    TOPIC = "topic"
    PILLAR = "pillar"
    HOOK_STYLE = "hook_style"
    CTA = "cta"
    TIMING = "timing"


class LearningStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class ExplanationGenerationSource(StrEnum):
    """Provenance of `Learning.explanation`, mirroring
    `ContentOpportunity.RationaleGenerationSource` -- `pattern_description`
    and `confidence_level` are always deterministic; only the natural
    -language `explanation` text may come from the `learning_explanation` AI
    task. `DETERMINISTIC` covers both the templated text written at
    extraction time and the fallback when the AI provider fails.
    """

    AI = "ai"
    DETERMINISTIC = "deterministic"


class Learning(Base):
    __tablename__ = "learnings"
    __table_args__ = (
        CheckConstraint(
            "confidence_level >= 0 AND confidence_level <= 1", name="ck_learning_confidence"
        ),
        # Makes the nightly extraction job idempotent: re-running it for the
        # same profile/dimension/value upserts the existing row instead of
        # creating a duplicate.
        UniqueConstraint(
            "profile_id", "dimension", "dimension_value", name="uq_learning_profile_dimension_value"
        ),
        # The scorer's per-opportunity lookup (app/ai/strategy/
        # opportunity_scorer.py) filters on exactly these three columns, on
        # every opportunity creation/update -- must stay a cheap indexed
        # read, not a scan.
        Index("ix_learnings_profile_status_dimension", "profile_id", "status", "dimension"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[LearningDimension] = mapped_column(SqlEnum(LearningDimension), nullable=False)
    dimension_value: Mapped[str] = mapped_column(String(128), nullable=False)
    pattern_description: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_generation_source: Mapped[ExplanationGenerationSource] = mapped_column(
        SqlEnum(ExplanationGenerationSource),
        nullable=False,
        default=ExplanationGenerationSource.DETERMINISTIC,
    )
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    json_type = JSON().with_variant(JSONB, "postgresql")
    supporting_evidence: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
    status: Mapped[LearningStatus] = mapped_column(
        SqlEnum(LearningStatus), nullable=False, default=LearningStatus.ACTIVE, index=True
    )
    extraction_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="learning_extraction_v1"
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
