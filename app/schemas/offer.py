from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OfferCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = Field(None, max_length=5000)
    offer_type: str | None = Field(None, max_length=255)
    value: float | None = None
    currency: str | None = Field(None, max_length=3)
    terms: Any = None
    target_audience: Any = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True


class OfferUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    offer_type: str | None = Field(None, max_length=255)
    value: float | None = None
    currency: str | None = Field(None, max_length=3)
    terms: Any = None
    target_audience: Any = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool | None = None


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_context_id: UUID
    name: str
    description: str | None
    offer_type: str | None
    value: float | None
    currency: str | None
    terms: Any
    target_audience: Any
    starts_at: datetime | None
    ends_at: datetime | None
    active: bool
    created_at: datetime
    updated_at: datetime
