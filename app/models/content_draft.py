import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_brief import ContentBrief
    from app.models.content_draft_variation import ContentDraftVariation
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
    __table_args__ = (
        # Supports the Day 19 default cursor-paginated library view (list
        # by profile/status ordered by recency); id as the final column
        # backs the (sort_key, id) cursor tie-break for stable ordering.
        sa.Index(
            "ix_content_drafts_profile_status_created_id",
            "profile_id",
            "status",
            sa.text("created_at DESC"),
            "id",
        ),
        # Postgres: a real GIN index over the generated tsvector column
        # (added by migration `u4v5w6x7y8`, not by the SQLAlchemy metadata
        # here — see that migration for why). On SQLite (test DB, built
        # from this metadata via `create_all`) this is just a harmless
        # plain index over the equivalent plain-text column declared below;
        # search on SQLite falls back to LIKE in the repository instead.
        sa.Index(
            "ix_content_drafts_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

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
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # Populated exclusively by the Postgres `GENERATED ALWAYS AS (...) STORED`
    # column added in migration `u4v5w6x7y8` (never assigned to from Python,
    # so the ORM never fights the database's own generated value). On SQLite
    # this is a plain, always-NULL text column -- full-text search there
    # falls back to LIKE in the repository. Never exposed on any response
    # schema.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"), nullable=True
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
    variations: Mapped[list["ContentDraftVariation"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", lazy="selectin"
    )
