import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_opportunity import ContentOpportunity
    from app.models.content_profile import ContentProfile


class AudienceSignalType(StrEnum):
    QUESTION = "question"


class AudienceSignalIntent(StrEnum):
    LEARN = "learn"
    COMPARE = "compare"
    SOLVE = "solve"
    DISCOVER = "discover"
    VALIDATE = "validate"
    ENTERTAIN = "entertain"


class AudienceSignalStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class AudienceSignalSource(StrEnum):
    MANUAL = "manual"


class AudienceSignal(Base):
    __tablename__ = "audience_signals"
    __table_args__ = (
        CheckConstraint(
            "strength_score >= 0 AND strength_score <= 1",
            name="ck_audience_signal_strength_score",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_type: Mapped[AudienceSignalType] = mapped_column(
        SqlEnum(AudienceSignalType), nullable=False, default=AudienceSignalType.QUESTION, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[AudienceSignalIntent] = mapped_column(
        SqlEnum(AudienceSignalIntent), nullable=False, index=True
    )
    strength_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, index=True)
    status: Mapped[AudienceSignalStatus] = mapped_column(
        SqlEnum(AudienceSignalStatus),
        nullable=False,
        default=AudienceSignalStatus.ACTIVE,
        index=True,
    )
    source: Mapped[AudienceSignalSource] = mapped_column(
        SqlEnum(AudienceSignalSource),
        nullable=False,
        default=AudienceSignalSource.MANUAL,
        index=True,
    )
    json_type = JSON().with_variant(JSONB, "postgresql")
    signal_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    profile: Mapped["ContentProfile"] = relationship(
        back_populates="audience_signals", lazy="selectin"
    )
    opportunities: Mapped[list["ContentOpportunity"]] = relationship(
        back_populates="audience_signal", lazy="selectin"
    )
