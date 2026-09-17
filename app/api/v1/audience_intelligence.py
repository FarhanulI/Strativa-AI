from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.models.content_profile import ContentProfile
from app.schemas.audience_intelligence import (
    AudienceIntelligenceCreate,
    AudienceIntelligenceResponse,
    AudienceIntelligenceUpdate,
)
from app.services.audience_intelligence import AudienceIntelligenceService

router = APIRouter(
    prefix="/profiles/{profile_id}/audience-intelligence",
    tags=["Audience Intelligence"],
)


async def get_audience_intelligence_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AudienceIntelligenceService:
    return AudienceIntelligenceService(session)


@router.post("", response_model=AudienceIntelligenceResponse, status_code=status.HTTP_201_CREATED)
async def create_audience_intelligence(
    payload: AudienceIntelligenceCreate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[AudienceIntelligenceService, Depends(get_audience_intelligence_service)],
) -> AudienceIntelligenceResponse:
    try:
        audience_intelligence = await service.create(
            profile_id=profile.id,
            workspace_id=profile.workspace_id,
            summary=payload.summary,
            language=payload.language,
            geography=payload.geography,
            demographics=payload.demographics,
            psychographics=payload.psychographics,
            behaviors=payload.behaviors,
            content_preferences=payload.content_preferences,
        )
        return AudienceIntelligenceResponse.model_validate(audience_intelligence)
    except ValueError as e:
        if "Audience intelligence already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Audience intelligence already exists for this content profile.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        ) from e


@router.get("", response_model=AudienceIntelligenceResponse)
async def get_audience_intelligence(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[AudienceIntelligenceService, Depends(get_audience_intelligence_service)],
) -> AudienceIntelligenceResponse:
    audience_intelligence = await service.get(
        profile_id=profile.id, workspace_id=profile.workspace_id
    )
    if not audience_intelligence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found",
        )
    return AudienceIntelligenceResponse.model_validate(audience_intelligence)


@router.patch("", response_model=AudienceIntelligenceResponse)
async def update_audience_intelligence(
    payload: AudienceIntelligenceUpdate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[AudienceIntelligenceService, Depends(get_audience_intelligence_service)],
) -> AudienceIntelligenceResponse:
    audience_intelligence = await service.update(
        profile_id=profile.id,
        workspace_id=profile.workspace_id,
        summary=payload.summary,
        language=payload.language,
        geography=payload.geography,
        demographics=payload.demographics,
        psychographics=payload.psychographics,
        behaviors=payload.behaviors,
        content_preferences=payload.content_preferences,
    )
    if not audience_intelligence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found",
        )
    return AudienceIntelligenceResponse.model_validate(audience_intelligence)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audience_intelligence(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[AudienceIntelligenceService, Depends(get_audience_intelligence_service)],
) -> None:
    success = await service.delete(profile_id=profile.id, workspace_id=profile.workspace_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found",
        )
