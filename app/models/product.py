import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.business_context import BusinessContext


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business_contexts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Text fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pricing
    price: Mapped[float | None] = mapped_column(Numeric(precision=10, scale=2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")

    # JSONB fields for structured data
    features: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    benefits: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    target_audience: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(
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
    business_context: Mapped["BusinessContext"] = relationship(
        back_populates="products",
        lazy="selectin",
    )
