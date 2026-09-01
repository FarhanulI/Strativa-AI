from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrandCreate(BaseModel):
    positioning: str | None = Field(None, max_length=5000)
    mission: str | None = Field(None, max_length=5000)
    vision: str | None = Field(None, max_length=5000)
    unique_selling_proposition: str | None = Field(None, max_length=5000)
    values: Any = None
    personality: Any = None
    voice: Any = None
    tone: Any = None
    messaging_guidelines: Any = None
    visual_identity: Any = None


class BrandUpdate(BaseModel):
    positioning: str | None = Field(None, max_length=5000)
    mission: str | None = Field(None, max_length=5000)
    vision: str | None = Field(None, max_length=5000)
    unique_selling_proposition: str | None = Field(None, max_length=5000)
    values: Any = None
    personality: Any = None
    voice: Any = None
    tone: Any = None
    messaging_guidelines: Any = None
    visual_identity: Any = None


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_profile_id: UUID
    positioning: str | None
    mission: str | None
    vision: str | None
    unique_selling_proposition: str | None
    values: Any
    personality: Any
    voice: Any
    tone: Any
    messaging_guidelines: Any
    visual_identity: Any
    created_at: datetime
    updated_at: datetime
