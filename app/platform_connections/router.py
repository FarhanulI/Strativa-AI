"""Platform-connection endpoints (Day 23).

Every route is nested under `/profiles/{profile_id}/...`, mirroring the
ownership chain, so Day 21's `require_profile_access` applies natively --
`profile_id` is validated against the caller's real `WorkspaceMember` row
on every call and 404s on any mismatch. No route accepts a bare,
client-trusted `workspace_id`/`profile_id`.

Putting `profile_id` in the path *and* inside the signed state is
deliberate belt-and-braces: the path value is what the caller is
authorized against, the state value is what the flow was started for, and
the service rejects the request unless they are the same profile. That is
what stops a forged or replayed state from attaching a connection to
someone else's profile.

No endpoint here accepts or returns a token.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.infrastructure.redis_client import get_redis
from app.models.content_profile import ContentProfile
from app.platform_connections.crypto import TokenEncryptionError
from app.platform_connections.models import SocialPlatform
from app.platform_connections.oauth import OAuthConfigurationError, OAuthExchangeError
from app.platform_connections.oauth.base import MissingDestinationTokenError
from app.platform_connections.pending import PendingConnectionNotFoundError
from app.platform_connections.schemas import (
    AuthorizeRequest,
    AuthorizeResponse,
    AvailableDestination,
    DestinationSelectionRequest,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    PlatformConnectionResponse,
)
from app.platform_connections.service import (
    ConnectionConflictError,
    ConnectionNotFoundError,
    DestinationNotAvailableError,
    NoAvailableDestinationsError,
    PlatformConnectionService,
    RedirectUriNotAllowedError,
    StateProfileMismatchError,
)
from app.platform_connections.state import InvalidOAuthStateError

router = APIRouter(tags=["Platform Connections"])


async def get_platform_connection_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlatformConnectionService:
    return PlatformConnectionService(session)


def error_response(error: Exception) -> HTTPException:
    """Map domain errors to status codes.

    `StateProfileMismatchError` is a 400, not a 403/404: by the time it can
    be raised the caller has already proven membership of the path profile
    via `require_profile_access`, so nothing about another tenant's
    existence is disclosed by saying the supplied state was for a different
    profile.
    """
    if isinstance(error, RedirectUriNotAllowedError | InvalidOAuthStateError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    if isinstance(error, StateProfileMismatchError | DestinationNotAvailableError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    if isinstance(error, PendingConnectionNotFoundError | ConnectionNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, ConnectionConflictError):
        # A concurrent selection won the race -- a retryable conflict, not a
        # server fault (matches the Day 13 variation-selection precedent).
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, NoAvailableDestinationsError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, MissingDestinationTokenError):
        # The platform owes us a destination-scoped credential and didn't
        # supply one. Refusing is deliberate: falling back to the
        # account-wide user token is exactly what must not happen.
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The platform did not return a credential for that destination",
        )
    if isinstance(error, OAuthConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform OAuth is not configured for this deployment",
        )
    if isinstance(error, OAuthExchangeError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The platform rejected the authorization request",
        )
    if isinstance(error, TokenEncryptionError):
        # Never surface the underlying message -- it concerns key material.
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored credential could not be processed",
        )
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.post(
    "/profiles/{profile_id}/platform-connections/{platform}/authorize",
    response_model=AuthorizeResponse,
)
async def start_authorization(
    platform: SocialPlatform,
    payload: AuthorizeRequest,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[PlatformConnectionService, Depends(get_platform_connection_service)],
) -> AuthorizeResponse:
    try:
        url, state, scopes = service.build_authorization(
            profile=profile, platform=platform, redirect_uri=payload.redirect_uri
        )
    except (ValueError, OAuthConfigurationError) as error:
        raise error_response(error) from error

    return AuthorizeResponse(authorization_url=url, state=state, platform=platform, scopes=scopes)


@router.post(
    "/profiles/{profile_id}/platform-connections/{platform}/callback",
    response_model=OAuthCallbackResponse,
)
async def oauth_callback(
    platform: SocialPlatform,
    payload: OAuthCallbackRequest,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[PlatformConnectionService, Depends(get_platform_connection_service)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> OAuthCallbackResponse:
    """Exchange the code and return the destinations to choose between.

    Deliberately does NOT create a `PlatformConnection`. One login can
    administer several Pages/Channels; which one this profile publishes to
    is the caller's decision, made at `/select-destination`.
    """
    try:
        selection_token, ttl, destinations = await service.handle_callback(
            profile=profile,
            platform=platform,
            state=payload.state,
            code=payload.code,
            redirect_uri=payload.redirect_uri,
            redis=redis,
        )
    except (ValueError, OAuthConfigurationError, OAuthExchangeError) as error:
        raise error_response(error) from error

    return OAuthCallbackResponse(
        selection_token=selection_token,
        expires_in_seconds=ttl,
        platform=platform,
        profile_id=profile.id,
        destinations=[
            AvailableDestination(
                external_account_id=destination.external_account_id,
                external_account_name=destination.external_account_name,
                metadata=destination.metadata,
            )
            for destination in destinations
        ],
    )


@router.post(
    "/profiles/{profile_id}/platform-connections/{platform}/select-destination",
    response_model=PlatformConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def select_destination(
    platform: SocialPlatform,
    payload: DestinationSelectionRequest,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[PlatformConnectionService, Depends(get_platform_connection_service)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> PlatformConnectionResponse:
    try:
        connection = await service.select_destination(
            profile=profile,
            platform=platform,
            selection_token=payload.selection_token,
            external_account_id=payload.external_account_id,
            redis=redis,
        )
    except (ValueError, TokenEncryptionError, MissingDestinationTokenError) as error:
        raise error_response(error) from error

    return PlatformConnectionResponse.model_validate(connection)


@router.get(
    "/profiles/{profile_id}/platform-connections",
    response_model=list[PlatformConnectionResponse],
)
async def list_platform_connections(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[PlatformConnectionService, Depends(get_platform_connection_service)],
) -> list[PlatformConnectionResponse]:
    connections = await service.list_connections(profile.id)
    return [PlatformConnectionResponse.model_validate(item) for item in connections]


@router.delete(
    "/profiles/{profile_id}/platform-connections/{platform}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect_platform(
    platform: SocialPlatform,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[PlatformConnectionService, Depends(get_platform_connection_service)],
) -> None:
    try:
        await service.disconnect(profile=profile, platform=platform)
    except ValueError as error:
        raise error_response(error) from error
