import asyncio

import pytest
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool


async def test_pool_exhaustion_raises_timeout_instead_of_hanging_or_crashing(tmp_path) -> None:
    """A pool sized too small for concurrent demand should degrade
    gracefully — a bounded, catchable TimeoutError on checkout — rather than
    hanging forever or taking down the process.
    """
    db_path = tmp_path / "pool_test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
    )

    held_connection = await engine.connect()
    try:
        with pytest.raises(SATimeoutError):
            await asyncio.wait_for(engine.connect(), timeout=2)
    finally:
        await held_connection.close()

    # The pool recovers once the held connection is released.
    recovered = await engine.connect()
    await recovered.close()
    await engine.dispose()
