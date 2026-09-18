from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import get_current_workspace
from app.core.database import get_db_session
from app.models.workspace import Workspace
from app.onboarding.schemas import (
    OnboardingAudienceRequest,
    OnboardingAudienceResponse,
    OnboardingBrandRequest,
    OnboardingBrandResponse,
    OnboardingCompleteResponse,
    OnboardingGoalsRequest,
    OnboardingGoalsResponse,
    OnboardingIdentityRequest,
    OnboardingIdentityResponse,
    OnboardingPlatformsRequest,
    OnboardingPlatformsResponse,
    OnboardingStateResponse,
)
from app.onboarding.service import (
    OnboardingIdentityRequiredError,
    OnboardingIncompleteError,
    OnboardingService,
)
from app.schemas.content_profile import ContentProfileResponse

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


async def get_onboarding_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OnboardingService:
    return OnboardingService(session)


@router.get("", response_model=OnboardingStateResponse)
async def get_onboarding(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingStateResponse:
    return OnboardingStateResponse.model_validate(await service.get_state(workspace))


@router.put("/identity", response_model=OnboardingIdentityResponse)
async def update_identity(
    payload: OnboardingIdentityRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingIdentityResponse:
    profile = await service.update_identity(workspace, payload)
    return OnboardingIdentityResponse(
        profile_id=profile.id,
        name=profile.name,
        positioning=profile.positioning,
        primary_niche=profile.primary_niche,
        topics=profile.topics,
        expertise=profile.expertise,
    )


@router.put("/audience", response_model=OnboardingAudienceResponse)
async def update_audience(
    payload: OnboardingAudienceRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingAudienceResponse:
    try:
        audience, pain_points, questions = await service.update_audience(workspace, payload)
    except OnboardingIdentityRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return OnboardingAudienceResponse(
        target_audience_description=audience.summary,
        interests=(audience.psychographics or {}).get("interests"),
        pain_points=[pp.title for pp in pain_points],
        questions=[q.question for q in questions],
    )


@router.put("/goals", response_model=OnboardingGoalsResponse)
async def update_goals(
    payload: OnboardingGoalsRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingGoalsResponse:
    try:
        profile = await service.update_goals(workspace, payload)
    except OnboardingIdentityRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return OnboardingGoalsResponse(goals=profile.goals or [])


@router.put("/brand", response_model=OnboardingBrandResponse)
async def update_brand(
    payload: OnboardingBrandRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingBrandResponse:
    try:
        brand = await service.update_brand(workspace, payload)
    except OnboardingIdentityRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return OnboardingBrandResponse(
        tone=(brand.tone or {}).get("tone_words"),
        style=(brand.messaging_guidelines or {}).get("style"),
        things_to_avoid=(brand.messaging_guidelines or {}).get("things_to_avoid"),
    )


@router.put("/platforms", response_model=OnboardingPlatformsResponse)
async def update_platforms(
    payload: OnboardingPlatformsRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingPlatformsResponse:
    try:
        profile = await service.update_platforms(workspace, payload)
    except OnboardingIdentityRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return OnboardingPlatformsResponse(platforms=profile.platforms or [])


@router.post("/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingCompleteResponse:
    try:
        profile = await service.complete(workspace)
    except OnboardingIncompleteError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Onboarding is incomplete", "missing": e.missing},
        ) from e
    return OnboardingCompleteResponse(
        onboarding_status=workspace.onboarding_status,
        profile=ContentProfileResponse.model_validate(profile),
    )
