import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.audience_intelligence import AudienceIntelligence
    from app.models.audience_signal import AudienceSignal
    from app.models.brand import Brand
    from app.models.business_context import BusinessContext
    from app.models.content_brief import ContentBrief
    from app.models.content_draft import ContentDraft
    from app.models.content_opportunity import ContentOpportunity
    from app.models.content_performance import ContentPerformance
    from app.models.market_intelligence import MarketIntelligence
    from app.models.workspace import Workspace


class ContentProfileType(StrEnum):
    CREATOR = "creator"
    BUSINESS = "business"


class ContentProfile(Base):
    # ContentProfile is intentionally universal so creators and businesses
    # share one strategic root for future intelligence and strategy modules.
    __tablename__ = "content_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[ContentProfileType] = mapped_column(SqlEnum(ContentProfileType), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_niche: Mapped[str | None] = mapped_column(String(255), nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    topics: Mapped[list[Any] | None] = mapped_column(json_type, nullable=True)
    expertise: Mapped[list[Any] | None] = mapped_column(json_type, nullable=True)
    goals: Mapped[list[Any] | None] = mapped_column(json_type, nullable=True)
    platforms: Mapped[list[Any] | None] = mapped_column(json_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    workspace: Mapped["Workspace"] = relationship(
        back_populates="content_profiles", lazy="selectin"
    )
    brand: Mapped["Brand | None"] = relationship(
        back_populates="content_profile",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    business_context: Mapped["BusinessContext | None"] = relationship(
        back_populates="content_profile",
        lazy="noload",
        uselist=False,
        cascade="all, delete-orphan",
    )
    audience_intelligence: Mapped["AudienceIntelligence | None"] = relationship(
        back_populates="content_profile",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    market_intelligence: Mapped["MarketIntelligence | None"] = relationship(
        back_populates="content_profile",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    opportunities: Mapped[list["ContentOpportunity"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    briefs: Mapped[list["ContentBrief"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
    drafts: Mapped[list["ContentDraft"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
    audience_signals: Mapped[list["AudienceSignal"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    performance_records: Mapped[list["ContentPerformance"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
