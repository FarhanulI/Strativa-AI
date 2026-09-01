import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AudienceIntelligence(Base):
    # Audience Intelligence belongs to ContentProfile, not BusinessContext.
    # This allows creators and businesses to use the same audience strategy system.
    __tablename__ = "audience_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geography: Mapped[str | None] = mapped_column(Text, nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    demographics: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    psychographics: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    behaviors: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    content_preferences: Mapped[dict | None] = mapped_column(json_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    from app.models.content_profile import ContentProfile

    content_profile: Mapped["ContentProfile"] = relationship(
        back_populates="audience_intelligence",
        lazy="selectin",
    )
    personas: Mapped[list["Persona"]] = relationship(
        back_populates="audience_intelligence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    pain_points: Mapped[list["PainPoint"]] = relationship(
        back_populates="audience_intelligence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    desires: Mapped[list["Desire"]] = relationship(
        back_populates="audience_intelligence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    questions: Mapped[list["AudienceQuestion"]] = relationship(
        back_populates="audience_intelligence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    objections: Mapped[list["AudienceObjection"]] = relationship(
        back_populates="audience_intelligence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audience_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audience_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    demographics: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    psychographics: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    goals: Mapped[list | None] = mapped_column(json_type, nullable=True)
    pain_points: Mapped[list | None] = mapped_column(json_type, nullable=True)
    desires: Mapped[list | None] = mapped_column(json_type, nullable=True)
    behaviors: Mapped[list | None] = mapped_column(json_type, nullable=True)
    content_preferences: Mapped[list | None] = mapped_column(json_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    audience_intelligence: Mapped["AudienceIntelligence"] = relationship(
        back_populates="personas",
        lazy="selectin",
    )


class PainPoint(Base):
    __tablename__ = "pain_points"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audience_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audience_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    severity: Mapped[int | None] = mapped_column(nullable=True)
    frequency: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    audience_intelligence: Mapped["AudienceIntelligence"] = relationship(
        back_populates="pain_points",
        lazy="selectin",
    )


class Desire(Base):
    __tablename__ = "desires"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audience_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audience_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    importance: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    audience_intelligence: Mapped["AudienceIntelligence"] = relationship(
        back_populates="desires",
        lazy="selectin",
    )


class AudienceQuestion(Base):
    __tablename__ = "audience_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audience_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audience_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    frequency: Mapped[int | None] = mapped_column(nullable=True)
    importance: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    audience_intelligence: Mapped["AudienceIntelligence"] = relationship(
        back_populates="questions",
        lazy="selectin",
    )


class AudienceObjection(Base):
    __tablename__ = "audience_objections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audience_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audience_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    severity: Mapped[int | None] = mapped_column(nullable=True)
    frequency: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    audience_intelligence: Mapped["AudienceIntelligence"] = relationship(
        back_populates="objections",
        lazy="selectin",
    )
