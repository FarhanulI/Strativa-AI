from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentPerformanceCreate(BaseModel):
    external_post_id: str | None = Field(None, max_length=255)
    platform: str = Field(..., min_length=1, max_length=64)
    content_type: str | None = Field(None, max_length=64)
    topic: str | None = None
    format: str | None = Field(None, max_length=64)
    hook: str | None = None
    published_at: datetime | None = None
    content_item_id: UUID | None = None
    views: int | None = Field(None, ge=0)
    reach: int | None = Field(None, ge=0)
    impressions: int | None = Field(None, ge=0)
    likes: int | None = Field(None, ge=0)
    comments: int | None = Field(None, ge=0)
    shares: int | None = Field(None, ge=0)
    saves: int | None = Field(None, ge=0)
    clicks: int | None = Field(None, ge=0)
    conversions: int | None = Field(None, ge=0)
    watch_time_seconds: float | None = Field(None, ge=0)
    average_watch_time_seconds: float | None = Field(None, ge=0)
    completion_rate: float | None = Field(None, ge=0, le=1)
    retention_rate: float | None = Field(None, ge=0, le=1)
    performance_metadata: dict[str, Any] | None = None


class ContentPerformanceUpdate(ContentPerformanceCreate):
    platform: str | None = Field(None, min_length=1, max_length=64)


class ContentPerformanceResponse(ContentPerformanceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    published_content_id: UUID | None = None
    reporting_period: date | None = None
    created_at: datetime
    updated_at: datetime


class PerformanceMetricsEntryCreate(BaseModel):
    """Manual metrics entry attached to a specific PublishedContent record
    (Day 25). `reporting_period` is required -- it, together with the
    published_content_id from the URL, is what the database-level unique
    constraint enforces against concurrent duplicate submissions.
    """

    reporting_period: date
    views: int | None = Field(None, ge=0)
    reach: int | None = Field(None, ge=0)
    likes: int | None = Field(None, ge=0)
    comments: int | None = Field(None, ge=0)
    shares: int | None = Field(None, ge=0)
    saves: int | None = Field(None, ge=0)
    watch_time_seconds: float | None = Field(None, ge=0)
    retention_rate: float | None = Field(None, ge=0, le=1)


class PerformanceMetricsEntryResponse(BaseModel):
    status: str = "pending"
    content_performance_id: UUID
    job_id: UUID
    job_status: str


class PerformanceAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    content_performance_id: UUID
    engagement_rate: float | None
    share_rate: float | None
    save_rate: float | None
    comment_rate: float | None
    click_through_rate: float | None
    conversion_rate: float | None
    baseline_engagement_rate: float | None
    baseline_share_rate: float | None
    baseline_save_rate: float | None
    baseline_retention_rate: float | None
    relative_engagement: float | None
    relative_shares: float | None
    relative_saves: float | None
    relative_retention: float | None
    performance_classification: str | None
    baseline_available: bool
    comparables_count: int
    evidence: dict[str, Any] | None
    analysis_version: str
    created_at: datetime
    updated_at: datetime


class PerformanceAnalysisPendingResponse(BaseModel):
    status: str = "pending"
    content_performance_id: UUID
    job_id: UUID
    job_status: str


class PerformanceInsightLLMResult(BaseModel):
    insight_type: str
    summary: str
    likely_reason: str
    strategic_learning: str
    recommended_action: str
    confidence_score: float = Field(..., ge=0, le=1)


class PerformanceInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    performance_analysis_id: UUID
    insight_type: str
    summary: str
    likely_reason: str
    strategic_learning: str
    recommended_action: str
    confidence_score: float
    evidence: dict[str, Any] | None
    model_provider: str
    model_name: str
    prompt_version: str
    status: str
    created_at: datetime
    updated_at: datetime
