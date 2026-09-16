from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.content_brief import BriefStatus, GenerationSource
from app.models.content_opportunity import (
    OpportunityPriority,
    OpportunitySource,
    OpportunityStatus,
    TargetObjective,
)
from app.schemas.content_draft import ContentDraftResponse


class ContentBriefLineageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    core_message: str
    angle: str | None
    target_objective: TargetObjective
    recommended_platform: str
    recommended_format: str | None
    status: BriefStatus
    generation_source: GenerationSource
    created_at: datetime


class ContentOpportunityLineageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    source_signal: OpportunitySource
    strategic_rationale: str
    target_objective: TargetObjective
    priority: OpportunityPriority
    status: OpportunityStatus
    opportunity_score: float
    relevance_score: float
    created_at: datetime


class ContentLibraryItemResponse(BaseModel):
    draft: ContentDraftResponse
    brief: ContentBriefLineageSummary
    opportunity: ContentOpportunityLineageSummary


class ContentLibraryListResponse(BaseModel):
    items: list[ContentDraftResponse]
    next_cursor: str | None = None
    has_more: bool = False
