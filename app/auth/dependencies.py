"""Reusable FastAPI dependency for JWT-authenticated requests.

This is the ONLY place that combines signature/expiry verification
(app.auth.jwt.decode_access_token) with the Redis revocation check --
every authenticated router should depend on `get_current_user`, not call
`decode_access_token` directly. Day 21's ownership-chain checks are
expected to build on top of the `AuthenticatedUser` this returns, not
replace it.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import InvalidTokenError, decode_access_token, extract_bearer_token
from app.auth.repository import UserRepository
from app.core.database import get_db_session
from app.infrastructure.redis_client import get_redis

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    workspace_ids: list[str]
    """Fast-path hint only -- see app/auth/jwt.py module docstring. Never
    sufficient by itself to authorize access to a specific workspace's
    resource (Day 21 not shipped yet)."""


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthenticatedUser:
    token = extract_bearer_token(request)
    if token is None:
        raise _CREDENTIALS_ERROR

    try:
        claims = decode_access_token(token)
    except InvalidTokenError as exc:
        raise _CREDENTIALS_ERROR from exc

    if await redis.exists(f"revoked_jti:{claims.jti}"):
        raise _CREDENTIALS_ERROR

    try:
        user_id = uuid.UUID(claims.sub)
    except ValueError as exc:
        raise _CREDENTIALS_ERROR from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise _CREDENTIALS_ERROR

    return AuthenticatedUser(id=str(user.id), email=user.email, workspace_ids=claims.workspace_ids)
