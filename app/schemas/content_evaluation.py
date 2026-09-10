from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_evaluation import (
    EvaluationClassification,
    EvaluationDimension,
    EvaluationSeverity,
)


# === AI-specific schemas (for LLM response validation) ===


class ScoreResult(BaseModel):
    """Score result from the LLM for a single dimension."""

    score: float = Field(..., ge=0.0, le=1.0, description="Score from 0.0 to 1.0")
    explanation: str = Field(..., description="Explanation of why this score was given")


class EvaluationFindingResult(BaseModel):
    """Finding result from the LLM."""

    dimension: EvaluationDimension
    severity: EvaluationSeverity
    summary: str = Field(..., max_length=255, description="Brief summary of the finding")
    explanation: str = Field(..., description="Detailed explanation")
    recommendation: str = Field(
        ..., description="Actionable recommendation (execution-focused, not strategy-redefining)"
    )


class ContentEvaluationLLMResult(BaseModel):
    """Structured response from LLM for content evaluation."""

    strategic_alignment: ScoreResult
    audience_relevance: ScoreResult
    hook_strength: ScoreResult
    message_clarity: ScoreResult
    narrative_coherence: ScoreResult
    format_alignment: ScoreResult
    emotional_alignment: ScoreResult
    cta_alignment: ScoreResult
    brand_alignment: ScoreResult
    findings: list[EvaluationFindingResult]


# === API schemas (for HTTP requests/responses) ===


class ContentEvaluationCreateRequest(BaseModel):
    """Request to create an evaluation for a draft."""

    use_ai: bool = Field(True, description="Whether to use AI for enrichment (fallback to deterministic if unavailable)")
    variation_id: UUID | None = Field(
        None, description="Optional: ID of specific variation to evaluate"
    )


class ContentEvaluationFindingResponse(BaseModel):
    """Single evaluation finding in response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_id: UUID
    dimension: EvaluationDimension
    severity: EvaluationSeverity
    summary: str
    explanation: str
    recommendation: str
    created_at: datetime


class ContentEvaluationResponse(BaseModel):
    """Full evaluation response with all scores and findings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    draft_id: UUID
    variation_id: UUID | None

    # Dimension scores
    strategic_alignment_score: float
    audience_relevance_score: float
    hook_strength_score: float
    message_clarity_score: float
    narrative_coherence_score: float
    format_alignment_score: float
    emotional_alignment_score: float
    cta_alignment_score: float
    brand_alignment_score: float

    # Overall classification
    overall_score: float
    classification: EvaluationClassification

    # Generation metadata
    generation_source: str
    ai_provider: str | None
    ai_model: str | None
    prompt_version: str | None

    # Findings and metadata
    findings: list[ContentEvaluationFindingResponse]
    evaluation_metadata: dict[str, Any] | None

    created_at: datetime
    updated_at: datetime


class ContentEvaluationListResponse(BaseModel):
    """List response with pagination."""

    model_config = ConfigDict(from_attributes=True)

    evaluations: list[ContentEvaluationResponse]
    total: int
    skip: int
    limit: int
