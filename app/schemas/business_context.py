from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BusinessContextCreate(BaseModel):
    commercial_objectives: Any = None
    target_market: str | None = Field(None, max_length=5000)
    pricing_position: str | None = Field(None, max_length=5000)


class BusinessContextUpdate(BaseModel):
    commercial_objectives: Any = None
    target_market: str | None = Field(None, max_length=5000)
    pricing_position: str | None = Field(None, max_length=5000)


class BusinessContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_profile_id: UUID
    commercial_objectives: Any
    target_market: str | None
    pricing_position: str | None
    created_at: datetime
    updated_at: datetime
