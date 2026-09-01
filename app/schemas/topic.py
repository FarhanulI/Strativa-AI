from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TopicCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)


class TopicUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    market_intelligence_id: UUID
    name: str
    description: str | None
    relevance_score: float | None
    created_at: datetime
    updated_at: datetime
