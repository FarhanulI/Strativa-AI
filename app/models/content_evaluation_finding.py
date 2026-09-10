import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.content_evaluation import EvaluationDimension, EvaluationSeverity

if TYPE_CHECKING:
    from app.models.content_evaluation import ContentEvaluation


class ContentEvaluationFinding(Base):
    """
    A single finding or observation from a content evaluation.

    Each evaluation can have multiple findings, allowing detailed feedback.
    """

    __tablename__ = "content_evaluation_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    dimension: Mapped[EvaluationDimension] = mapped_column(
        SqlEnum(EvaluationDimension), nullable=False, index=True
    )
    severity: Mapped[EvaluationSeverity] = mapped_column(
        SqlEnum(EvaluationSeverity), nullable=False, index=True
    )

    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
    )

    # Relationship
    evaluation: Mapped["ContentEvaluation"] = relationship(back_populates="findings")
