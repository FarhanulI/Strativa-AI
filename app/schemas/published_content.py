from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.published_content import PublishMethod, PublishStatus
from app.schemas.content_draft import ContentDraftResponse
from app.schemas.content_library import ContentBriefLineageSummary, ContentOpportunityLineageSummary


class PublishedContentCreate(BaseModel):
    external_url: str | None = Field(None, min_length=1, max_length=2048)


class PublishedContentScheduleCreate(BaseModel):
    scheduled_at: datetime
    external_url: str | None = Field(None, min_length=1, max_length=2048)


class PublishedContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: UUID
    profile_id: UUID
    platform: str
    external_url: str | None
    scheduled_at: datetime | None
    published_at: datetime | None
    publish_method: PublishMethod
    status: PublishStatus
    published_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class PublishedContentLineageResponse(BaseModel):
    published: PublishedContentResponse
    draft: ContentDraftResponse
    brief: ContentBriefLineageSummary
    opportunity: ContentOpportunityLineageSummary
