from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    demographics: dict | None = None
    psychographics: dict | None = None
    goals: list | None = None
    pain_points: list | None = None
    desires: list | None = None
    behaviors: list | None = None
    content_preferences: list | None = None


class PersonaUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    demographics: dict | None = None
    psychographics: dict | None = None
    goals: list | None = None
    pain_points: list | None = None
    desires: list | None = None
    behaviors: list | None = None
    content_preferences: list | None = None


class PersonaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audience_intelligence_id: UUID
    name: str
    description: str | None
    demographics: dict | None
    psychographics: dict | None
    goals: list | None
    pain_points: list | None
    desires: list | None
    behaviors: list | None
    content_preferences: list | None
    created_at: datetime
    updated_at: datetime
