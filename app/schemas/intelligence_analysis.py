from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntelligenceInsightItem(BaseModel):
    summary: str
    rationale: str


class IntelligenceAnalysisLLMResult(BaseModel):
    """Structured AI output. `grounded_on` is never taken from this model —
    the service always substitutes the deterministic list of record ids it
    fetched, so the LLM cannot fabricate lineage."""

    insights: list[IntelligenceInsightItem] = Field(..., min_length=1)


class IntelligenceAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    insights: list[dict[str, Any]]
    grounded_on: list[str]
    generation_source: str
    grounding_basis: str | None = None
    is_current: bool
    analysis_version: str
    generated_at: datetime


class IntelligenceAnalysisPendingResponse(BaseModel):
    status: str = "pending"
    job_id: UUID
    job_status: str
