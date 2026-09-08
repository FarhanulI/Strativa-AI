import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.content_opportunity import TargetObjective

if TYPE_CHECKING:
    from app.models.audience_intelligence import AudienceQuestion, Desire, PainPoint, Persona
    from app.models.content_draft import ContentDraft
    from app.models.content_opportunity import ContentOpportunity
    from app.models.content_profile import ContentProfile


class BriefStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    ARCHIVED = "archived"


class GenerationSource(StrEnum):
    MANUAL = "manual"
    DETERMINISTIC = "deterministic"
    AI_ASSISTED = "ai_assisted"


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    core_message: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    big_idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategic_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    target_objective: Mapped[TargetObjective] = mapped_column(
        SqlEnum(TargetObjective), nullable=False, index=True
    )
    target_persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_pain_point_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pain_points.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_desire_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("desires.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_audience_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audience_questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recommended_format: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    recommended_platform: Mapped[str] = mapped_column(
        String(32), nullable=False, default="other", server_default="other", index=True
    )
    recommended_length: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    key_points: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)
    supporting_context: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)
    success_criteria: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)
    brief_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    generation_source: Mapped[GenerationSource] = mapped_column(
        SqlEnum(GenerationSource), nullable=False, index=True
    )
    status: Mapped[BriefStatus] = mapped_column(
        SqlEnum(BriefStatus), nullable=False, default=BriefStatus.DRAFT, index=True
    )
    brief_metadata: Mapped[dict[str, Any] | None] = mapped_column(
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

    profile: Mapped["ContentProfile"] = relationship(back_populates="briefs", lazy="selectin")
    opportunity: Mapped["ContentOpportunity"] = relationship(
        back_populates="briefs", lazy="selectin"
    )
    drafts: Mapped[list["ContentDraft"]] = relationship(
        back_populates="brief", cascade="all, delete-orphan", lazy="selectin"
    )
    target_persona: Mapped["Persona | None"] = relationship(lazy="selectin")
    target_pain_point: Mapped["PainPoint | None"] = relationship(lazy="selectin")
    target_desire: Mapped["Desire | None"] = relationship(lazy="selectin")
    target_audience_question: Mapped["AudienceQuestion | None"] = relationship(lazy="selectin")
