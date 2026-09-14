from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db_session
from app.infrastructure.jobs.pool import get_arq_pool
from app.main import app


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
