from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentIntelligenceSynthesisLLMResult(BaseModel):
    """Structured AI output. `supporting_analyses` is never taken from this
    model -- the service always substitutes the deterministic list of
    component-analysis ids it fetched, so the LLM cannot fabricate lineage.
    """

    summary: str
    key_themes: list[str] = Field(..., min_length=1)


class ContentIntelligenceSynthesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    summary: str
    key_themes: list[str]
    supporting_analyses: list[str]
    generation_source: str
    is_current: bool
    is_stale: bool
    cold_start: bool
    synthesis_version: str
    generated_at: datetime


class ContentIntelligenceSynthesisPendingResponse(BaseModel):
    status: str = "pending"
    job_id: UUID
    job_status: str
