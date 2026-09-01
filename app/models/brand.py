import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_profile import ContentProfile


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    # Text fields
    positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision: Mapped[str | None] = mapped_column(Text, nullable=True)
    unique_selling_proposition: Mapped[str | None] = mapped_column(Text, nullable=True)

    json_type = JSON().with_variant(JSONB, "postgresql")

    # JSONB fields for structured data
    values: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    personality: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    voice: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    tone: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    messaging_guidelines: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    visual_identity: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)

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
        back_populates="brand",
        lazy="selectin",
    )
