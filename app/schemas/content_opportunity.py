from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_opportunity import (
    OpportunityPriority,
    OpportunitySource,
    OpportunityStatus,
    TargetObjective,
)


class ContentOpportunityCreate(BaseModel):
    source_signal: OpportunitySource
    market_signal_id: UUID | None = None
    audience_signal_id: UUID | None = None
    performance_insight_id: UUID | None = None
    title: str = Field(..., min_length=1)
    target_objective: TargetObjective
    recommended_format: str | None = Field(None, max_length=64)


class ContentOpportunityUpdate(BaseModel):
    title: str | None = Field(None, min_length=1)
    target_objective: TargetObjective | None = None
    recommended_format: str | None = Field(None, max_length=64)
    status: OpportunityStatus | None = None


class ContentOpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    market_signal_id: UUID | None
    audience_signal_id: UUID | None
    performance_insight_id: UUID | None
    source_signal: OpportunitySource
    title: str
    strategic_rationale: str
    target_objective: TargetObjective
    recommended_format: str | None
    relevance_score: float
    opportunity_score: float
    priority: OpportunityPriority
    status: OpportunityStatus
    expires_at: datetime | None
    opportunity_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
