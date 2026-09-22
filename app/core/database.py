from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    # Every migration defines timestamp columns as `TIMESTAMP WITH TIME
    # ZONE`; without this, SQLAlchemy's default `datetime` -> `DateTime()`
    # mapping produces a naive column type, which asyncpg then rejects when
    # binding the timezone-aware `datetime.now(UTC)` values models actually
    # pass (invisible on SQLite, which doesn't distinguish the two).
    type_annotation_map = {datetime: DateTime(timezone=True)}


def _engine_kwargs() -> dict:
    """Pool/timeout kwargs, sized per docs/development/progress.md "Database
    Migration: PostgreSQL -> Neon". Only applied for the asyncpg (Postgres)
    driver — SQLite (used by some test infra) does not support server-side
    statement_timeout or a multi-connection pool in the same sense.
    """
    if not settings.database_url.startswith("postgresql"):
        return {}
    return {
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout_seconds,
        "connect_args": {
            # Neon requires TLS. asyncpg's connect() takes an `ssl` kwarg,
            # not `sslmode` — the `?sslmode=require` query string Neon's
            # console gives you is NOT honored by SQLAlchemy's asyncpg
            # dialect the way it is for psycopg2, so it must be set here
            # explicitly.
            "ssl": "require",
            # Disables asyncpg's client-side prepared-statement cache.
            # Required under PgBouncer transaction-pooling mode: PgBouncer
            # can hand a different backend connection to each statement
            # within a session, so a client-cached prepared statement can
            # silently reference a statement the current backend never
            # prepared. This is the one real session-affinity hazard in
            # this codebase (no advisory locks/LISTEN-NOTIFY/explicit
            # PREPARE exist anywhere in app/).
            "statement_cache_size": 0,
            # `statement_timeout` here is a Postgres session-level *query
            # execution* timeout, applied once when the connection opens —
            # it bounds how long a query is allowed to run, not how long
            # acquiring a connection takes. It is unrelated to, and not at
            # risk of being tripped by, Neon's autosuspend cold-start
            # latency (the delay before a suspended branch's compute wakes
            # up), which only affects connection *acquisition* time.
            "server_settings": {"statement_timeout": str(settings.db_statement_timeout_ms)},
        },
    }


engine = create_async_engine(settings.database_url, **_engine_kwargs())
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
