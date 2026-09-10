from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_draft import CompositionMode, DraftGenerationSource, DraftStatus


class ContentCreationLLMResult(BaseModel):
    title: str | None = None
    hook: str = Field(min_length=1)
    body: str = Field(min_length=1)
    cta: str | None = None


class ContentDraftCreate(BaseModel):
    composition_mode: CompositionMode = CompositionMode.COMPOSE
    use_ai: bool = False
    title: str | None = Field(None, min_length=1)
    hook: str | None = Field(None, min_length=1)
    body: str | None = Field(None, min_length=1)
    cta: str | None = Field(None, min_length=1)


class ContentDraftUpdate(BaseModel):
    title: str | None = Field(None, min_length=1)
    hook: str | None = Field(None, min_length=1)
    body: str | None = Field(None, min_length=1)
    cta: str | None = Field(None, min_length=1)
    status: DraftStatus | None = None


class ContentDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    brief_id: UUID
    platform: str
    format: str
    title: str | None
    hook: str
    body: str
    cta: str | None
    caption: str | None
    status: DraftStatus
    generation_source: DraftGenerationSource
    composition_mode: CompositionMode
    ai_provider: str | None
    ai_model: str | None
    prompt_version: str | None
    draft_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


DraftStatusFilter = Literal["draft", "ready", "approved", "archived"]
