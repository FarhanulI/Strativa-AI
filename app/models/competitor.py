import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.market_intelligence import MarketIntelligence


class Competitor(Base):
    # A Competitor is any external profile relevant for benchmarking:
    # rival brand, similar creator, niche leader, or inspiration account.
    __tablename__ = "competitors"
    __table_args__ = (
        # NULL profile_url is treated as distinct in Postgres/SQLite unique
        # semantics, so this constraint prevents obvious duplicates while
        # still allowing multiple competitors with no URL recorded.
        UniqueConstraint(
            "market_intelligence_id",
            "platform",
            "profile_url",
            name="uq_competitors_market_platform_url",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    market_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_intelligence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    niche: Mapped[str | None] = mapped_column(Text, nullable=True)

    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")
    competitor_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    market_intelligence: Mapped["MarketIntelligence"] = relationship(
        back_populates="competitors",
        lazy="selectin",
    )
