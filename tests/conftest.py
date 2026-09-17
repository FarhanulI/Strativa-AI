import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import fakeredis.aioredis as fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.infrastructure.ratelimit.middleware as ratelimit_middleware
from app.auth.jwt import encode_access_token
from app.auth.models import User
from app.auth.security import hash_password
from app.core.database import Base, get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.infrastructure.redis_client import get_redis
from app.main import app
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session using SQLite in-memory"""
    # Use SQLite in-memory database for testing
    # This avoids the need for a running PostgreSQL instance
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with async_session_factory() as session:
        yield session

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_db(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Backward-compatible alias for the shared test database session."""
    yield db_session


@pytest.fixture
def override_get_db(test_db: AsyncSession):
    """Override the get_db_session dependency"""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db

    app.dependency_overrides[get_db_session] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _default_arq_pool_override():
    """Content opportunity creation fans out an `opportunity_reasoning` job
    (see docs/development/day-18.md), which requires an arq pool. No real
    Redis/arq worker is available in this test environment, so every test
    gets a mocked pool by default; a test that needs to assert on job
    submission can override `app.dependency_overrides[get_arq_pool]` itself
    (see tests/test_opportunity_reasoning.py), which simply replaces this
    default for the duration of that test.
    """
    pool = AsyncMock()
    app.dependency_overrides[get_arq_pool] = lambda: pool
    yield pool
    app.dependency_overrides.pop(get_arq_pool, None)


@pytest.fixture(autouse=True)
def _default_cache_redis_override(monkeypatch: pytest.MonkeyPatch):
    """Content draft create/update and variation selection invalidate the
    Content Library cache (see docs/development/day-19.md), which requires
    a Redis client. No real Redis is available in this development
    environment, so every test gets a fake one by default via this
    conftest-level patch; tests/test_content_library.py additionally
    patches the same target (applied after this one, per pytest's
    conftest-before-local autouse ordering) so it can assert against cache
    hits/invalidation with its own fake instance.
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.services.content_library.get_redis", lambda: fake)
    yield fake


@pytest.fixture
async def client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """An HTTP client wired to the test DB session via `override_get_db`,
    for tests that exercise auth endpoints end-to-end.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _default_auth_redis_override(monkeypatch: pytest.MonkeyPatch):
    """JWT revocation (app/auth/dependencies.py, app/auth/service.py) and the
    Day 15 rate-limit middleware's identity bucket both read the shared Redis
    connection (see docs/development/day-20.md — auth must reuse the Day 15
    connection, not create a second client). No real Redis is available in
    this test environment, so every test gets one fake instance shared by
    both the FastAPI-dependency path (via `app.dependency_overrides`) and the
    middleware's direct `get_redis()` call (via monkeypatch, since it is not
    dependency-injected).
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake
    monkeypatch.setattr(ratelimit_middleware, "get_redis", lambda: fake)
    yield fake
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
async def seed_workspace(db_session: AsyncSession) -> Workspace:
    workspace = Workspace(name="Acme Co", slug="acme-co")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def seed_user(db_session: AsyncSession, seed_workspace: Workspace) -> User:
    """A pre-seeded, existing user with a known plaintext password
    (`_SEED_USER_PASSWORD`), already a member of `seed_workspace`. Day 20 has
    no signup endpoint (MVP: one User maps to exactly one Workspace) -- tests
    seed User/Workspace directly, matching the Days 15-19 convention.
    """
    user = User(email="test.user@example.com", hashed_password=hash_password(_SEED_USER_PASSWORD))
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        WorkspaceMember(
            workspace_id=seed_workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


_SEED_USER_PASSWORD = "correct-horse-battery-staple"


async def authenticate_as_workspace_owner(
    client: AsyncClient, db_session: AsyncSession, workspace_id: uuid.UUID
) -> User:
    """Seed a fresh User + owning WorkspaceMember for `workspace_id` and set
    `client`'s default Authorization header so every subsequent request from
    it is authenticated as that user (see app/authz/dependencies.py — Day 21
    routes 404 for a caller with no WorkspaceMember row for the workspace).
    """
    user = User(
        email=f"{uuid.uuid4().hex}@example.com",
        hashed_password=hash_password(_SEED_USER_PASSWORD),
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    token, _jti, _exp = encode_access_token(user.id, uuid.uuid4(), [str(workspace_id)])
    client.headers["Authorization"] = f"Bearer {token}"
    return user
