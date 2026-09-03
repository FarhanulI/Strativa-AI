from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.audience_signal import (
    AudienceSignalIntent,
    AudienceSignalSource,
    AudienceSignalStatus,
    AudienceSignalType,
)


class AudienceSignalCreate(BaseModel):
    signal_type: AudienceSignalType = AudienceSignalType.QUESTION
    question: str = Field(..., min_length=1)
    topic: str | None = None
    description: str | None = None
    intent: AudienceSignalIntent
    strength_score: float = Field(0.5, ge=0.0, le=1.0)
    status: AudienceSignalStatus = AudienceSignalStatus.ACTIVE
    source: AudienceSignalSource = AudienceSignalSource.MANUAL
    signal_metadata: dict[str, Any] | None = None
    observed_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "AudienceSignalCreate":
        if (
            self.expires_at is not None
            and self.observed_at is not None
            and self.expires_at < self.observed_at
        ):
            raise ValueError("expires_at must be greater than or equal to observed_at")
        return self


class AudienceSignalUpdate(BaseModel):
    signal_type: AudienceSignalType | None = None
    question: str | None = Field(None, min_length=1)
    topic: str | None = None
    description: str | None = None
    intent: AudienceSignalIntent | None = None
    strength_score: float | None = Field(None, ge=0.0, le=1.0)
    status: AudienceSignalStatus | None = None
    source: AudienceSignalSource | None = None
    signal_metadata: dict[str, Any] | None = None
    observed_at: datetime | None = None
    expires_at: datetime | None = None


class AudienceSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    signal_type: AudienceSignalType
    question: str
    topic: str | None
    description: str | None
    intent: AudienceSignalIntent
    strength_score: float
    status: AudienceSignalStatus
    source: AudienceSignalSource
    signal_metadata: dict[str, Any] | None
    observed_at: datetime
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
