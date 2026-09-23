import asyncio
import uuid

import fakeredis.aioredis as fakeredis
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import decode_access_token
from app.auth.models import User
from app.auth.service import AuthService, EmailAlreadyRegisteredError
from app.core.config import settings
from app.models.workspace import Workspace, WorkspaceOnboardingStatus
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


async def test_register_creates_user_workspace_and_owner_membership(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new.user@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    claims = decode_access_token(body["access_token"])

    users = (
        (await db_session.execute(select(User).where(User.email == "new.user@example.com")))
        .scalars()
        .all()
    )
    assert len(users) == 1
    user = users[0]
    assert claims.sub == str(user.id)

    members = (
        (
            await db_session.execute(
                select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(members) == 1
    assert members[0].role == WorkspaceRole.OWNER

    workspace = await db_session.get(Workspace, members[0].workspace_id)
    assert workspace is not None
    assert workspace.onboarding_status == WorkspaceOnboardingStatus.NOT_STARTED


async def test_register_duplicate_email_rejected_without_duplicate_records(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@example.com", "password": "correct-horse-battery"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@example.com", "password": "another-password-456"},
    )
    assert second.status_code == 409

    users = (
        (await db_session.execute(select(User).where(User.email == "dupe@example.com")))
        .scalars()
        .all()
    )
    assert len(users) == 1

    workspaces = (await db_session.execute(select(Workspace))).scalars().all()
    assert len(workspaces) == 1


async def test_register_duplicate_email_case_insensitive(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "Mixed.Case@example.com", "password": "correct-horse-battery"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "mixed.case@example.com", "password": "another-password-456"},
    )
    assert second.status_code == 409


async def test_register_rate_limited_after_threshold(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.infrastructure.ratelimit.middleware.settings.rate_limit_enabled", True)
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.auth_register_rate_limit_requests_per_window",
        2,
    )
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.auth_register_rate_limit_window_seconds",
        60,
    )

    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "rate1@example.com", "password": "correct-horse-battery"},
    )
    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "rate2@example.com", "password": "correct-horse-battery"},
    )
    third = await client.post(
        "/api/v1/auth/register",
        json={"email": "rate3@example.com", "password": "correct-horse-battery"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429


async def test_register_then_onboarding_status_is_not_started(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "onboarding.status@example.com", "password": "correct-horse-battery"},
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    status_response = await client.get("/api/v1/onboarding")

    assert status_response.status_code == 200
    assert status_response.json()["onboarding_status"] == "not_started"


async def test_register_retries_on_workspace_slug_collision(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slug collision on flush/commit must be retried with a fresh slug
    rather than misreported as a taken email (Issue 1) -- exercised here by
    forcing `_generate_workspace_slug` to return the same, pre-taken value
    on the first call and a fresh one on the retry.
    """
    colliding_slug = f"colliding-{uuid.uuid4().hex[:8]}"
    db_session.add(Workspace(name="Existing", slug=colliding_slug))
    await db_session.commit()

    slugs = iter([colliding_slug, f"retry-{uuid.uuid4().hex[:8]}"])
    monkeypatch.setattr(
        "app.auth.service._generate_workspace_slug", lambda email: next(slugs)
    )

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "slug.collision@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workspace"] is not None

    workspace = await db_session.get(Workspace, uuid.UUID(body["workspace"]["id"]))
    assert workspace is not None
    assert workspace.slug != colliding_slug


async def test_register_unrecognized_integrity_error_propagates(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An `IntegrityError` from an unrecognized constraint must not be
    misreported as either an email or slug conflict (Issue 1) -- it should
    propagate as-is so it isn't silently swallowed.
    """

    class _FakeDiag:
        constraint_name = "some_unrelated_constraint"

    class _FakeOrig(Exception):
        diag = _FakeDiag()

    async def _raise_integrity_error(*args, **kwargs):
        raise IntegrityError("INSERT", {}, _FakeOrig())

    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    service = AuthService(db_session, fake_redis)
    monkeypatch.setattr(db_session, "commit", _raise_integrity_error)

    with pytest.raises(IntegrityError):
        await service.register("unrecognized.constraint@example.com", "correct-horse-battery")


async def test_register_concurrent_same_email_exactly_one_succeeds(
    db_session: AsyncSession,
) -> None:
    """Two truly concurrent registrations for the same email must resolve
    to exactly one success and one 409-equivalent rejection, with no
    duplicate User/Workspace rows left behind (Issue 9).

    This needs two independent DB connections/transactions (not the
    single SAVEPOINT-scoped `db_session` connection) to race for real, so
    it opens its own engine and cleans up the rows it writes explicitly
    afterward instead of relying on `db_session`'s outer-transaction
    rollback.
    """
    email = f"concurrent.{uuid.uuid4().hex[:8]}@example.com"
    engine = create_async_engine(settings.test_database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _attempt() -> None:
        async with session_factory() as session:
            fake_redis = fakeredis.FakeRedis(decode_responses=True)
            service = AuthService(session, fake_redis)
            await service.register(email, "correct-horse-battery")

    try:
        results = await asyncio.gather(_attempt(), _attempt(), return_exceptions=True)

        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, EmailAlreadyRegisteredError)]
        assert len(successes) == 1
        assert len(failures) == 1

        users = (
            (await db_session.execute(select(User).where(User.email == email)))
            .scalars()
            .all()
        )
        assert len(users) == 1

        members = (
            (
                await db_session.execute(
                    select(WorkspaceMember).where(WorkspaceMember.user_id == users[0].id)
                )
            )
            .scalars()
            .all()
        )
        workspace_ids = {member.workspace_id for member in members}
        assert len(workspace_ids) == 1
    finally:
        async with session_factory() as cleanup_session:
            user = (
                await cleanup_session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is not None:
                workspace_ids = (
                    await cleanup_session.execute(
                        select(WorkspaceMember.workspace_id).where(
                            WorkspaceMember.user_id == user.id
                        )
                    )
                ).scalars().all()
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
