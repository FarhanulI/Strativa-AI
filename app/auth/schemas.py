from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.workspace import WorkspaceOnboardingStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class WorkspaceSummary(BaseModel):
    id: UUID
    onboarding_status: WorkspaceOnboardingStatus


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    workspace: WorkspaceSummary | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str
