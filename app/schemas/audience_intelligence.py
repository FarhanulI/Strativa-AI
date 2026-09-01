from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AudienceIntelligenceCreate(BaseModel):
    summary: str | None = None
    language: str | None = Field(None, max_length=50)
    geography: str | None = None
    demographics: dict | None = None
    psychographics: dict | None = None
    behaviors: dict | None = None
    content_preferences: dict | None = None


class AudienceIntelligenceUpdate(BaseModel):
    summary: str | None = None
    language: str | None = Field(None, max_length=50)
    geography: str | None = None
    demographics: dict | None = None
    psychographics: dict | None = None
    behaviors: dict | None = None
    content_preferences: dict | None = None


class AudienceIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_profile_id: UUID
    summary: str | None
    language: str | None
    geography: str | None
    demographics: dict | None
    psychographics: dict | None
    behaviors: dict | None
    content_preferences: dict | None
    created_at: datetime
    updated_at: datetime
