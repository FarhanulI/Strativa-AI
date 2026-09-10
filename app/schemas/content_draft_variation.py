from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_draft_variation import VariationGenerationSource, VariationType


class ContentVariationLLMItem(BaseModel):
    content: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ContentVariationLLMResult(BaseModel):
    variations: list[ContentVariationLLMItem]


class ContentDraftVariationGenerateRequest(BaseModel):
    variation_type: VariationType
    count: int = Field(default=3, ge=1, le=5)
    use_ai: bool = True


class ContentDraftVariationSelectRequest(BaseModel):
    is_selected: bool


class ContentDraftVariationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: UUID
    variation_type: VariationType
    variation_index: int
    content: str
    rationale: str
    generation_source: VariationGenerationSource
    ai_provider: str | None
    ai_model: str | None
    prompt_version: str | None
    is_selected: bool
    created_at: datetime
    updated_at: datetime
