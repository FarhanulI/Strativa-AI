import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.market_intelligence import MarketIntelligence
    from app.models.topic import Topic


class MarketSignal(Base):
    # A MarketSignal is intelligence input only.
    # It is intentionally separated from ContentOpportunity, which will be
    # produced later by the Strategy/Opportunity engine after combining
    # signals with brand, audience, performance and goals.
    __tablename__ = "market_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    market_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # source_type and signal_type are kept as free-form strings so external
    # ingestion sources can extend them without a schema change.
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    velocity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    engagement_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active", index=True
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    signal_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    market_intelligence: Mapped["MarketIntelligence"] = relationship(
        back_populates="market_signals",
        lazy="selectin",
    )
    topic: Mapped["Topic | None"] = relationship(
        back_populates="market_signals",
        lazy="selectin",
    )
