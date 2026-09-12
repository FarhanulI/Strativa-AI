from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    """Pool/timeout kwargs, sized per docs/development/progress.md "Platform
    Infrastructure". Only applied for the asyncpg (Postgres) driver — SQLite
    (used by tests) does not support server-side statement_timeout or a
    multi-connection pool in the same sense.
    """
    if not settings.database_url.startswith("postgresql"):
        return {}
    return {
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout_seconds,
        "connect_args": {
            "server_settings": {"statement_timeout": str(settings.db_statement_timeout_ms)}
        },
    }


engine = create_async_engine(settings.database_url, **_engine_kwargs())
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
