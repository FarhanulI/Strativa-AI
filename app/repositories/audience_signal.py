from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_signal import AudienceSignal


class AudienceSignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal: AudienceSignal) -> AudienceSignal:
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def get_by_id(self, profile_id: UUID, signal_id: UUID) -> AudienceSignal | None:
        result = await self.session.execute(
            select(AudienceSignal).where(
                AudienceSignal.id == signal_id,
                AudienceSignal.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: UUID,
        signal_type: str | None = None,
        intent: str | None = None,
        status: str | None = None,
        source: str | None = None,
        sort_by: str = "observed_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[AudienceSignal]:
        statement = select(AudienceSignal).where(AudienceSignal.profile_id == profile_id)
        for field, value in (
            (AudienceSignal.signal_type, signal_type),
            (AudienceSignal.intent, intent),
            (AudienceSignal.status, status),
            (AudienceSignal.source, source),
        ):
            if value is not None:
                statement = statement.where(field == value)
        order_column = getattr(AudienceSignal, sort_by)
        statement = statement.order_by(
            order_column.desc() if sort_order == "desc" else order_column.asc()
        )
        result = await self.session.execute(statement.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(self, signal: AudienceSignal) -> AudienceSignal:
        await self.session.flush()
        return signal

    async def delete(self, signal: AudienceSignal) -> bool:
        await self.session.delete(signal)
        await self.session.flush()
        return True
