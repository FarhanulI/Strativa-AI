from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PainPointCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    evidence: str | None = None
    severity: int | None = Field(None, ge=1, le=5)
    frequency: int | None = Field(None, ge=1, le=5)


class PainPointUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    evidence: str | None = None
    severity: int | None = Field(None, ge=1, le=5)
    frequency: int | None = Field(None, ge=1, le=5)


class PainPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audience_intelligence_id: UUID
    title: str
    description: str | None
    evidence: str | None
    severity: int | None
    frequency: int | None
    created_at: datetime
    updated_at: datetime
