import asyncio
import uuid

import fakeredis.aioredis as fakeredis
import pytest
from fastapi import HTTPException, Request
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.dependencies import get_current_user
from app.auth.jwt import decode_access_token
from app.auth.models import RefreshToken, User
from app.auth.service import AuthService, InvalidRefreshTokenError
from app.core.config import settings
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _SEED_USER_PASSWORD


async def test_login_success_returns_token_pair(client: AsyncClient, seed_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0

    claims = decode_access_token(body["access_token"])
    assert claims.sub == str(seed_user.id)


async def test_login_wrong_password_rejected(client: AsyncClient, seed_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": "not-the-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_login_unknown_email_rejected_with_identical_message(
    client: AsyncClient, seed_user: User
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever12345"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_expired_access_token_rejected(
    client: AsyncClient,
    seed_user: User,
    db_session,
    _default_auth_redis_override: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.auth.jwt.settings.jwt_access_token_ttl_minutes", 0)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    access_token = login_response.json()["access_token"]

    await asyncio.sleep(1.1)

    request = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, session=db_session, redis=_default_auth_redis_override)
    assert exc_info.value.status_code == 401


async def test_refresh_issues_new_pair_and_rotates(client: AsyncClient, seed_user: User) -> None:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )

    assert refresh_response.status_code == 200
    new_body = refresh_response.json()
    assert new_body["access_token"] != login_response.json()["access_token"]
    assert new_body["refresh_token"] != old_refresh_token


async def test_reused_stale_refresh_token_rejected(client: AsyncClient, seed_user: User) -> None:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    first_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert first_refresh.status_code == 200

    replay_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert replay_response.status_code == 401


async def test_concurrent_refresh_same_token_only_one_wins_and_session_revoked(
    db_session: AsyncSession,
) -> None:
    """Two requests racing to rotate the SAME refresh token (e.g. a leaked
    token replayed by an attacker at nearly the same moment as the
    legitimate user's own refresh) must not both succeed -- see
    AuthService.refresh's claim_for_rotation. Exactly one wins the atomic
    claim; the loser is treated identically to a genuine replay, which
    revokes the entire session, so even the winner's newly-issued token
    stops working on a subsequent refresh.

    Like test_register_concurrent_same_email_exactly_one_succeeds in
    tests/test_registration.py, this needs two independent DB
    connections/transactions racing for real -- the single
    SAVEPOINT-scoped `db_session`/`client` connection can't be used
    concurrently by two in-flight requests at once (confirmed empirically:
    doing so raises `sqlalchemy.exc.InvalidRequestError: Session is
    already flushing`, since AsyncSession isn't reentrant). So this opens
    its own engine, provisions its own user via that engine (register,
    then login -- mirroring `seed_user` but via a real commit so a second
    connection can see it), and cleans up explicitly afterward instead of
    relying on `db_session`'s outer-transaction rollback.
    """
    email = f"concurrent.refresh.{uuid.uuid4().hex[:8]}@example.com"
    password = "correct-horse-battery"
    engine = create_async_engine(settings.test_database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as setup_session:
        await AuthService(setup_session, fakeredis.FakeRedis(decode_responses=True)).register(
            email, password
        )

    async with session_factory() as login_session:
        login_result = await AuthService(
            login_session, fakeredis.FakeRedis(decode_responses=True)
        ).login(email, password)
    refresh_token = login_result.refresh_token
    session_id = uuid.UUID(decode_access_token(login_result.access_token).sid)

    async def _attempt() -> tuple[str, str, int]:
        async with session_factory() as session:
            service = AuthService(session, fakeredis.FakeRedis(decode_responses=True))
            return await service.refresh(refresh_token)

    try:
        results = await asyncio.gather(_attempt(), _attempt(), return_exceptions=True)

        successes = [r for r in results if isinstance(r, tuple)]
        failures = [r for r in results if isinstance(r, InvalidRefreshTokenError)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert str(failures[0]) == "Refresh token has already been used"

        winning_refresh_token = successes[0][1]

        session_tokens = (
            (
                await db_session.execute(
                    select(RefreshToken).where(RefreshToken.session_id == session_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(session_tokens) >= 2
        assert all(token.revoked_at is not None for token in session_tokens)

        async with session_factory() as verify_session:
            verify_service = AuthService(verify_session, fakeredis.FakeRedis(decode_responses=True))
            with pytest.raises(InvalidRefreshTokenError, match="already been used"):
                await verify_service.refresh(winning_refresh_token)
    finally:
        async with session_factory() as cleanup_session:
            user = (
                await cleanup_session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is not None:
                await cleanup_session.execute(
                    delete(RefreshToken).where(RefreshToken.user_id == user.id)
                )
                workspace_ids = (
                    (
                        await cleanup_session.execute(
                            select(WorkspaceMember.workspace_id).where(
                                WorkspaceMember.user_id == user.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                await cleanup_session.execute(
                    delete(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
                )
                if workspace_ids:
                    await cleanup_session.execute(
                        delete(Workspace).where(Workspace.id.in_(workspace_ids))
                    )
                await cleanup_session.execute(delete(User).where(User.id == user.id))
                await cleanup_session.commit()
        await engine.dispose()


async def test_logout_revokes_token_and_immediate_next_request_rejected(
    client: AsyncClient,
    seed_user: User,
    db_session,
    _default_auth_redis_override: Redis,
) -> None:
    """No other protected route exists yet in Day 20's scope, so this
    exercises the reusable `get_current_user` dependency directly against
    the same Redis client the HTTP-driven logout call used -- that
    dependency is exactly what any future protected route (including Day
    21's ownership-chain checks) will depend on.
    """
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 200

    request = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, session=db_session, redis=_default_auth_redis_override)
    assert exc_info.value.status_code == 401


async def test_revoked_jti_present_in_redis_with_remaining_ttl(
    client: AsyncClient, seed_user: User, _default_auth_redis_override: Redis
) -> None:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]
    claims = decode_access_token(access_token)

    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    key = f"revoked_jti:{claims.jti}"
    assert await _default_auth_redis_override.exists(key)
    ttl = await _default_auth_redis_override.ttl(key)
    assert 0 < ttl <= 15 * 60


async def test_password_reset_end_to_end(
    client: AsyncClient, seed_user: User, db_session, _default_auth_redis_override: Redis
) -> None:
    request_response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": seed_user.email}
    )
    assert request_response.status_code == 200

    # The HTTP response never echoes the raw token (anti-enumeration) --
    # fetch it directly from the service layer for this end-to-end test.
    service = AuthService(db_session, _default_auth_redis_override)
    raw_token = await service.request_password_reset(seed_user.email)
    assert raw_token is not None

    confirm_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "brand-new-password-123"},
    )
    assert confirm_response.status_code == 200

    login_with_new_password = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": "brand-new-password-123"},
    )
    assert login_with_new_password.status_code == 200

    login_with_old_password = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    assert login_with_old_password.status_code == 401

    reuse_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "another-password-456"},
    )
    assert reuse_response.status_code == 400


async def test_password_reset_unknown_email_returns_generic_message(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}
    )

    assert response.status_code == 200
    assert "if an account" in response.json()["message"].lower()


async def test_login_rate_limited_after_threshold(
    client: AsyncClient, seed_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.infrastructure.ratelimit.middleware.settings.rate_limit_enabled", True)
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.auth_login_rate_limit_requests_per_window",
        2,
    )
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.auth_login_rate_limit_window_seconds",
        60,
    )

    payload = {"email": seed_user.email, "password": "wrong-password"}
    first = await client.post("/api/v1/auth/login", json=payload)
    second = await client.post("/api/v1/auth/login", json=payload)
    third = await client.post("/api/v1/auth/login", json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


async def test_rate_limiter_keys_off_authenticated_identity_not_header(
    client: AsyncClient, seed_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller presenting a valid access token is bucketed by their real
    JWT identity; a caller spoofing the old X-User-Id header without a
    real bearer token shares the anonymous/IP bucket instead.
    """
    monkeypatch.setattr("app.infrastructure.ratelimit.middleware.settings.rate_limit_enabled", True)
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.rate_limit_crud_requests_per_window", 2
    )
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.rate_limit_window_seconds", 60
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_user.email, "password": _SEED_USER_PASSWORD},
    )
    access_token = login_response.json()["access_token"]

    # Two requests with a spoofed X-User-Id header (no real bearer token)
    # share the anonymous/IP bucket and are limited after 2.
    await client.get("/", headers={"X-User-Id": "someone-else"})
    await client.get("/", headers={"X-User-Id": "someone-else"})
    third = await client.get("/", headers={"X-User-Id": "someone-else"})
    assert third.status_code == 429

    # A request with a real, valid bearer token gets its own bucket keyed
    # by verified identity, independent of the exhausted anonymous bucket
    # used above.
    authenticated = await client.get("/", headers={"Authorization": f"Bearer {access_token}"})
    assert authenticated.status_code == 200
