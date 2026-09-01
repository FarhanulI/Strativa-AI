import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_profile import ContentProfile
    from app.models.offer import Offer
    from app.models.product import Product
    from app.models.service import Service


class BusinessContext(Base):
    __tablename__ = "business_contexts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    # Text fields
    target_market: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_position: Mapped[str | None] = mapped_column(Text, nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")

    # JSONB field for structured commercial objectives
    commercial_objectives: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(
        json_type, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # Relationships
    content_profile: Mapped["ContentProfile"] = relationship(
        back_populates="business_context",
        lazy="selectin",
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="business_context",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    services: Mapped[list["Service"]] = relationship(
        back_populates="business_context",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    offers: Mapped[list["Offer"]] = relationship(
        back_populates="business_context",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
