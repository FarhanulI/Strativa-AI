import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.intelligence_analysis import AnalysisGenerationSource


class ContentIntelligenceSynthesis(Base):
    """The cross-domain "central brain" artifact: one row combining whatever
    Brand/Audience/Market/Performance analyses currently exist for a profile
    into a single grounded strategic summary.

    Historical rows are kept (`is_current` moves rather than being
    overwritten) per the architecture's data-lineage principle. `is_stale`
    is flipped by any component analysis's regeneration and checked lazily
    on the next GET, rather than regenerating eagerly on every component
    change, to avoid thundering-herd regeneration when several components
    change close together.
    """

    __tablename__ = "content_intelligence_synthesis"
    __table_args__ = (
        Index(
            "ix_content_intelligence_synthesis_profile_id_generated_at",
            "profile_id",
            "generated_at",
        ),
        Index(
            "ix_content_intelligence_synthesis_profile_id_is_current",
            "profile_id",
            "is_current",
        ),
        Index(
            "uq_content_intelligence_synthesis_current",
            "profile_id",
            unique=True,
            postgresql_where=sa.text("is_current = true"),
            sqlite_where=sa.text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    json_type = JSON().with_variant(JSONB, "postgresql")

    summary: Mapped[str] = mapped_column(sa.Text, nullable=False)
    key_themes: Mapped[list[Any]] = mapped_column(json_type, nullable=False, default=list)
    supporting_analyses: Mapped[list[Any]] = mapped_column(json_type, nullable=False, default=list)
    generation_source: Mapped[AnalysisGenerationSource] = mapped_column(
        SqlEnum(AnalysisGenerationSource), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    # True only when Brand/Audience/Market are all grounded and Performance
    # is absent specifically because the profile has published nothing yet
    # (see app.content_intelligence.grounding.gather_synthesis_grounding) --
    # never set retroactively on rows generated before this distinction
    # existed.
    cold_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    synthesis_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="strategic_synthesis_v1"
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
