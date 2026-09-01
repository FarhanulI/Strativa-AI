import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.competitor import Competitor
    from app.models.content_profile import ContentProfile
    from app.models.market_signal import MarketSignal
    from app.models.topic import Topic


class MarketIntelligence(Base):
    # MarketIntelligence belongs to ContentProfile, not BusinessContext.
    # Creators and businesses share the same market intelligence architecture.
    # This is intelligence input only — it does not generate ContentOpportunity
    # by itself. That is the future job of the Opportunity/Strategy engine.
    __tablename__ = "market_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    content_profile: Mapped["ContentProfile"] = relationship(
        back_populates="market_intelligence",
        lazy="selectin",
    )
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="market_intelligence",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    market_signals: Mapped[list["MarketSignal"]] = relationship(
        back_populates="market_intelligence",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="market_intelligence",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
