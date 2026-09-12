import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_draft import ContentDraft


class PublishStatus(StrEnum):
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    RETRACTED = "retracted"
    CANCELLED = "cancelled"


class PublishMethod(StrEnum):
    MANUAL = "manual"
    API = "api"


class PublishedContent(Base):
    __tablename__ = "published_content"
    __table_args__ = (Index("ix_published_content_status_scheduled_at", "status", "scheduled_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    publish_method: Mapped[PublishMethod] = mapped_column(
        SqlEnum(PublishMethod), nullable=False, default=PublishMethod.MANUAL
    )
    status: Mapped[PublishStatus] = mapped_column(
        SqlEnum(PublishStatus), nullable=False, default=PublishStatus.PUBLISHED, index=True
    )
    json_type = JSON().with_variant(JSONB, "postgresql")
    published_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", json_type, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    draft: Mapped["ContentDraft"] = relationship(lazy="selectin")
