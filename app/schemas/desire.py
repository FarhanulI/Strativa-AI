from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DesireCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    evidence: str | None = None
    importance: int | None = Field(None, ge=1, le=5)


class DesireUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    evidence: str | None = None
    importance: int | None = Field(None, ge=1, le=5)


class DesireResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audience_intelligence_id: UUID
    title: str
    description: str | None
    evidence: str | None
    importance: int | None
    created_at: datetime
    updated_at: datetime
