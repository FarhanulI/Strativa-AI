from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AudienceQuestionCreate(BaseModel):
    question: str = Field(..., min_length=1)
    context: str | None = None
    evidence: str | None = None
    frequency: int | None = Field(None, ge=1, le=5)
    importance: int | None = Field(None, ge=1, le=5)


class AudienceQuestionUpdate(BaseModel):
    question: str | None = Field(None, min_length=1)
    context: str | None = None
    evidence: str | None = None
    frequency: int | None = Field(None, ge=1, le=5)
    importance: int | None = Field(None, ge=1, le=5)


class AudienceQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audience_intelligence_id: UUID
    question: str
    context: str | None
    evidence: str | None
    frequency: int | None
    importance: int | None
    created_at: datetime
    updated_at: datetime
