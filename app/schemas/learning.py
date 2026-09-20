from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.learning import LearningDimension, LearningStatus


class LearningCreate(BaseModel):
    dimension: LearningDimension
    dimension_value: str = Field(..., min_length=1, max_length=128)
    pattern_description: str = Field(..., min_length=1)
    confidence_level: float = Field(..., ge=0, le=1)
    supporting_evidence: dict[str, Any] = Field(default_factory=dict)


class LearningUpdate(BaseModel):
    """Only `status` is client-updatable -- per Day 26 scope, supersession
    is a simple manual status flag, never an automatic recomputation of
    `pattern_description`/`confidence_level`/`supporting_evidence`, which
    are owned by the extraction job.
    """

    status: LearningStatus | None = None


class LearningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    dimension: LearningDimension
    dimension_value: str
    pattern_description: str
    explanation: str | None
    explanation_generation_source: str
    confidence_level: float
    supporting_evidence: dict[str, Any]
    status: LearningStatus
    extraction_version: str
    created_at: datetime
    updated_at: datetime


class LearningExplanationLLMResult(BaseModel):
    explanation: str
