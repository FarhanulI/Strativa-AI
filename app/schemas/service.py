from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = Field(None, max_length=5000)
    category: str | None = Field(None, max_length=255)
    price: float | None = None
    currency: str | None = Field(None, max_length=3)
    features: Any = None
    benefits: Any = None
    target_audience: Any = None


class ServiceUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    category: str | None = Field(None, max_length=255)
    price: float | None = None
    currency: str | None = Field(None, max_length=3)
    features: Any = None
    benefits: Any = None
    target_audience: Any = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_context_id: UUID
    name: str
    description: str | None
    category: str | None
    price: float | None
    currency: str | None
    features: Any
    benefits: Any
    target_audience: Any
    created_at: datetime
    updated_at: datetime
