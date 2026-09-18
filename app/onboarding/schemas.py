from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.workspace import WorkspaceOnboardingStatus
from app.schemas.content_profile import ContentProfileResponse


class OnboardingGoal(StrEnum):
    GROWTH = "growth"
    AUTHORITY = "authority"
    ENGAGEMENT = "engagement"
    COMMUNITY = "community"


class OnboardingPlatform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    X = "x"
    LINKEDIN = "linkedin"


class OnboardingIdentityRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    positioning: str | None = None
    primary_niche: str | None = Field(None, max_length=255)
    topics: list[str] | None = None
    expertise: list[str] | None = None


class OnboardingAudienceRequest(BaseModel):
    target_audience_description: str | None = None
    interests: list[str] | None = None
    pain_points: list[str] | None = None
    questions: list[str] | None = None


class OnboardingGoalsRequest(BaseModel):
    goals: list[OnboardingGoal] = Field(..., min_length=1)


class OnboardingBrandRequest(BaseModel):
    tone: list[str] | None = None
    style: str | None = None
    things_to_avoid: list[str] | None = None


class OnboardingPlatformsRequest(BaseModel):
    platforms: list[OnboardingPlatform] = Field(..., min_length=1)


class OnboardingIdentityResponse(BaseModel):
    profile_id: UUID
    name: str
    positioning: str | None
    primary_niche: str | None
    topics: list[str] | None
    expertise: list[str] | None


class OnboardingAudienceResponse(BaseModel):
    target_audience_description: str | None
    interests: list[str] | None
    pain_points: list[str]
    questions: list[str]


class OnboardingGoalsResponse(BaseModel):
    goals: list[str]


class OnboardingBrandResponse(BaseModel):
    tone: list[str] | None
    style: str | None
    things_to_avoid: list[str] | None


class OnboardingPlatformsResponse(BaseModel):
    platforms: list[str]


class OnboardingStateResponse(BaseModel):
    onboarding_status: WorkspaceOnboardingStatus
    identity: OnboardingIdentityResponse | None
    audience: OnboardingAudienceResponse | None
    goals: OnboardingGoalsResponse | None
    brand: OnboardingBrandResponse | None
    platforms: OnboardingPlatformsResponse | None


class OnboardingCompleteResponse(BaseModel):
    onboarding_status: WorkspaceOnboardingStatus
    profile: ContentProfileResponse
