from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_brief import BriefStatus, GenerationSource
from app.models.content_opportunity import TargetObjective


class BriefCompositionLLMResult(BaseModel):
    angle: str
    big_idea: str
    voice_guidelines: str
    key_points: list[str] = Field(max_length=5)
    supporting_context: list[str] = Field(max_length=5)


class ContentBriefCreate(BaseModel):
    opportunity_id: UUID
    composition_mode: Literal["compose", "manual"] = "compose"
    use_ai: bool = False
    title: str | None = Field(None, min_length=1)
    core_message: str | None = Field(None, min_length=1)
    angle: str | None = None
    big_idea: str | None = None
    target_objective: TargetObjective | None = None
    target_persona_id: UUID | None = None
    target_pain_point_id: UUID | None = None
    target_desire_id: UUID | None = None
    target_audience_question_id: UUID | None = None
    recommended_format: str | None = Field(None, max_length=64)
    recommended_platform: Literal[
        "facebook", "instagram", "tiktok", "youtube", "linkedin", "x", "other"
    ] = "other"
    recommended_length: str | None = Field(None, max_length=128)
    tone: str | None = None
    voice_guidelines: str | None = None
    cta_strategy: str | None = None
    key_points: list[str] | None = Field(None, max_length=5)
    supporting_context: list[str] | None = Field(None, max_length=5)
    success_criteria: list[str] | None = None


class ContentBriefUpdate(BaseModel):
    title: str | None = Field(None, min_length=1)
    core_message: str | None = Field(None, min_length=1)
    angle: str | None = None
    big_idea: str | None = None
    target_objective: TargetObjective | None = None
    target_persona_id: UUID | None = None
    target_pain_point_id: UUID | None = None
    target_desire_id: UUID | None = None
    target_audience_question_id: UUID | None = None
    recommended_format: str | None = Field(None, max_length=64)
    recommended_platform: (
        Literal["facebook", "instagram", "tiktok", "youtube", "linkedin", "x", "other"] | None
    ) = None
    recommended_length: str | None = Field(None, max_length=128)
    tone: str | None = None
    voice_guidelines: str | None = None
    cta_strategy: str | None = None
    key_points: list[str] | None = Field(None, max_length=5)
    supporting_context: list[str] | None = Field(None, max_length=5)
    success_criteria: list[str] | None = None
    status: BriefStatus | None = None


class ContentBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    opportunity_id: UUID
    title: str
    core_message: str
    angle: str | None
    big_idea: str | None
    strategic_rationale: str
    target_objective: TargetObjective
    target_persona_id: UUID | None
    target_pain_point_id: UUID | None
    target_desire_id: UUID | None
    target_audience_question_id: UUID | None
    recommended_format: str | None
    recommended_platform: str
    recommended_length: str | None
    tone: str | None
    voice_guidelines: str | None
    cta_strategy: str | None
    key_points: list[str] | None
    supporting_context: list[str] | None
    success_criteria: list[str] | None
    brief_version: str
    generation_source: GenerationSource
    status: BriefStatus
    brief_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
