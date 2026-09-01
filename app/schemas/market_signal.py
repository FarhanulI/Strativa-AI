from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarketSignalCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    topic_id: UUID | None = None
    source_type: str | None = Field(None, max_length=64)
    source_url: str | None = None
    signal_type: str | None = Field(None, max_length=64)
    velocity_score: float | None = Field(None, ge=0.0, le=1.0)
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    engagement_score: float | None = Field(None, ge=0.0, le=1.0)
    status: str | None = Field(None, max_length=32)
    detected_at: datetime | None = None
    expires_at: datetime | None = None
    signal_metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "MarketSignalCreate":
        if (
            self.expires_at is not None
            and self.detected_at is not None
            and self.expires_at < self.detected_at
        ):
            raise ValueError("expires_at must be greater than or equal to detected_at")
        return self


class MarketSignalUpdate(BaseModel):
    title: str | None = Field(None, min_length=1)
    description: str | None = None
    topic_id: UUID | None = None
    source_type: str | None = Field(None, max_length=64)
    source_url: str | None = None
    signal_type: str | None = Field(None, max_length=64)
    velocity_score: float | None = Field(None, ge=0.0, le=1.0)
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    engagement_score: float | None = Field(None, ge=0.0, le=1.0)
    status: str | None = Field(None, max_length=32)
    detected_at: datetime | None = None
    expires_at: datetime | None = None
    signal_metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "MarketSignalUpdate":
        if (
            self.expires_at is not None
            and self.detected_at is not None
            and self.expires_at < self.detected_at
        ):
            raise ValueError("expires_at must be greater than or equal to detected_at")
        return self


class MarketSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    market_intelligence_id: UUID
    topic_id: UUID | None
    title: str
    description: str | None
    source_type: str | None
    source_url: str | None
    signal_type: str | None
    velocity_score: float | None
    relevance_score: float | None
    engagement_score: float | None
    status: str
    detected_at: datetime
    expires_at: datetime | None
    signal_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
