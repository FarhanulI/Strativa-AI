from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import InvalidTokenError, extract_bearer_token
from app.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidResetTokenError,
)
from app.core.database import get_db_session
from app.infrastructure.redis_client import get_redis

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Generic, single message returned for every password-reset request
# outcome (unknown email or not) so the response cannot be used to
# enumerate registered accounts -- see AuthService.request_password_reset.
_RESET_REQUESTED_MESSAGE = MessageResponse(
    message="If an account with that email exists, a password reset link has been sent."
)

_MISSING_ACCESS_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Missing or invalid Authorization header",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    return AuthService(session, redis)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        access_token, refresh_token, expires_in = await service.login(
            payload.email, payload.password
        )
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        access_token, refresh_token, expires_in = await service.refresh(payload.refresh_token)
    except InvalidRefreshTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: LogoutRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    access_token = extract_bearer_token(request)
    if access_token is None:
        raise _MISSING_ACCESS_TOKEN

    try:
        await service.logout(access_token, payload.refresh_token)
    except InvalidTokenError as e:
        raise _MISSING_ACCESS_TOKEN from e
    return MessageResponse(message="Logged out")


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    payload: PasswordResetRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    # The raw token is intentionally discarded here -- see
    # AuthService.request_password_reset docstring. It must never be
    # returned in an HTTP response.
    await service.request_password_reset(payload.email)
    return _RESET_REQUESTED_MESSAGE


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    try:
        await service.confirm_password_reset(payload.token, payload.new_password)
    except InvalidResetTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return MessageResponse(message="Password has been reset")
