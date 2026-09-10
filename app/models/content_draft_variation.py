import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_draft import ContentDraft


class VariationType(StrEnum):
    HOOK = "hook"
    CAPTION = "caption"


class VariationGenerationSource(StrEnum):
    DETERMINISTIC = "deterministic"
    AI = "ai"


class ContentDraftVariation(Base):
    __tablename__ = "content_draft_variations"
    __table_args__ = (
        UniqueConstraint(
            "draft_id",
            "variation_type",
            "variation_index",
            name="uq_content_draft_variations_draft_type_index",
        ),
        CheckConstraint("variation_index >= 1", name="ck_content_draft_variations_index_positive"),
        sa.Index(
            "uq_content_draft_variations_selected",
            "draft_id",
            "variation_type",
            unique=True,
            postgresql_where=sa.text("is_selected = true"),
            sqlite_where=sa.text("is_selected = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variation_type: Mapped[VariationType] = mapped_column(
        SqlEnum(VariationType), nullable=False, index=True
    )
    variation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    generation_source: Mapped[VariationGenerationSource] = mapped_column(
        SqlEnum(VariationGenerationSource), nullable=False, index=True
    )
    ai_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    draft: Mapped["ContentDraft"] = relationship(back_populates="variations", lazy="selectin")
