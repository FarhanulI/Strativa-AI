from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MarketIntelligenceCreate(BaseModel):
    summary: str | None = None
    market_context: str | None = None


class MarketIntelligenceUpdate(BaseModel):
    summary: str | None = None
    market_context: str | None = None


class MarketIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_profile_id: UUID
    summary: str | None
    market_context: str | None
    created_at: datetime
    updated_at: datetime
