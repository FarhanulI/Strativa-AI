from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentProfileType(StrEnum):
    CREATOR = "creator"
    BUSINESS = "business"


class ContentProfileCreate(BaseModel):
    type: ContentProfileType
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    website: str | None = Field(None, max_length=2048)
    location: str | None = Field(None, max_length=255)
    positioning: str | None = None
    topics: list[str] | None = None
    expertise: list[str] | None = None
    goals: list[str] | None = None


class ContentProfileUpdate(BaseModel):
    type: ContentProfileType | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    website: str | None = Field(None, max_length=2048)
    location: str | None = Field(None, max_length=255)
    positioning: str | None = None
    topics: list[str] | None = None
    expertise: list[str] | None = None
    goals: list[str] | None = None


class ContentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    type: ContentProfileType
    name: str
    description: str | None
    website: str | None
    location: str | None
    positioning: str | None
    topics: list[str] | None
    expertise: list[str] | None
    goals: list[str] | None
    created_at: datetime
    updated_at: datetime
