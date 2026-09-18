"""Persistence for `PlatformConnection`. No authorization logic lives here
-- ownership is established above, in the router's Day 21 dependencies and
the service (see `app/platform_connections/service.py`), per the project's
Router -> Service -> Repository layering.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform_connections.models import ConnectionStatus, PlatformConnection, SocialPlatform


class PlatformConnectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, connection: PlatformConnection) -> PlatformConnection:
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def get_for_profile_platform(
        self, profile_id: UUID, platform: SocialPlatform
    ) -> PlatformConnection | None:
        result = await self.session.execute(
            select(PlatformConnection).where(
                PlatformConnection.profile_id == profile_id,
                PlatformConnection.platform == platform,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_profile(self, profile_id: UUID) -> list[PlatformConnection]:
        result = await self.session.execute(
            select(PlatformConnection)
            .where(PlatformConnection.profile_id == profile_id)
            .order_by(PlatformConnection.platform)
        )
        return list(result.scalars().all())

    async def list_due_for_refresh(
        self, *, due_before: datetime, limit: int
    ) -> list[PlatformConnection]:
        """Connections whose access token lapses within the refresh window.

        Matches the `(status, token_expires_at)` composite index on the
        model. Rows with a NULL `token_expires_at` are excluded on purpose:
        a Facebook/Instagram Page token derived from a long-lived user
        token does not expire, so it is not "due" and must not be dragged
        through a refresh that platform has no grant for.
        """
        result = await self.session.execute(
            select(PlatformConnection)
            .where(
                PlatformConnection.status == ConnectionStatus.CONNECTED,
                PlatformConnection.token_expires_at.is_not(None),
                PlatformConnection.token_expires_at <= due_before,
            )
            .order_by(PlatformConnection.token_expires_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete(self, connection: PlatformConnection) -> None:
        """A hard delete, never a soft one.

        Disconnect must actually remove the credential; flipping a status
        column while leaving a live, decryptable token in the table would
        leave exactly the dangling credential this day is meant to avoid.
        """
        await self.session.delete(connection)
        await self.session.flush()

    async def update(self, connection: PlatformConnection) -> PlatformConnection:
        await self.session.flush()
        return connection
