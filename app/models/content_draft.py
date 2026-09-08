import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_brief import ContentBrief
    from app.models.content_profile import ContentProfile


class DraftStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    ARCHIVED = "archived"


class DraftGenerationSource(StrEnum):
    DETERMINISTIC = "deterministic"
    AI = "ai"
    AI_FALLBACK = "ai_fallback"
    MANUAL = "manual"


class CompositionMode(StrEnum):
    COMPOSE = "compose"
    MANUAL = "manual"


class ContentDraft(Base):
    __tablename__ = "content_drafts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brief_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_briefs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        SqlEnum(DraftStatus), nullable=False, default=DraftStatus.DRAFT, index=True
    )
    generation_source: Mapped[DraftGenerationSource] = mapped_column(
        SqlEnum(DraftGenerationSource), nullable=False, index=True
    )
    composition_mode: Mapped[CompositionMode] = mapped_column(
        SqlEnum(CompositionMode), nullable=False, default=CompositionMode.COMPOSE
    )
    ai_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    json_type = JSON().with_variant(JSONB, "postgresql")
    draft_metadata: Mapped[dict[str, Any] | None] = mapped_column(
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

    profile: Mapped["ContentProfile"] = relationship(back_populates="drafts", lazy="selectin")
    brief: Mapped["ContentBrief"] = relationship(back_populates="drafts", lazy="selectin")
