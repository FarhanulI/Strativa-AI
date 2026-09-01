from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompetitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    platform: str | None = Field(None, max_length=64)
    profile_url: str | None = None
    niche: str | None = None
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    competitor_metadata: dict[str, Any] | None = None


class CompetitorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    platform: str | None = Field(None, max_length=64)
    profile_url: str | None = None
    niche: str | None = None
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    competitor_metadata: dict[str, Any] | None = None


class CompetitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    market_intelligence_id: UUID
    name: str
    description: str | None
    platform: str | None
    profile_url: str | None
    niche: str | None
    relevance_score: float | None
    competitor_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
