import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.market_intelligence import MarketIntelligence
    from app.models.market_signal import MarketSignal


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint(
            "market_intelligence_id",
            "name",
            name="uq_topics_market_intelligence_id_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    market_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    market_intelligence: Mapped["MarketIntelligence"] = relationship(
        back_populates="topics",
        lazy="selectin",
    )
    market_signals: Mapped[list["MarketSignal"]] = relationship(
        back_populates="topic",
        lazy="selectin",
    )
