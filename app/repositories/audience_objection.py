from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceObjection


class AudienceObjectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, objection: AudienceObjection) -> AudienceObjection:
        self.session.add(objection)
        await self.session.flush()
        return objection

    async def get_by_id(self, objection_id: UUID) -> AudienceObjection | None:
        stmt = select(AudienceObjection).where(AudienceObjection.id == objection_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_audience(
        self, audience_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[AudienceObjection]:
        stmt = (
            select(AudienceObjection)
            .where(AudienceObjection.audience_intelligence_id == audience_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, objection: AudienceObjection) -> AudienceObjection:
        await self.session.merge(objection)
        await self.session.flush()
        return objection

    async def delete(self, objection_id: UUID) -> bool:
        stmt = select(AudienceObjection).where(AudienceObjection.id == objection_id)
        result = await self.session.execute(stmt)
        objection = result.scalar_one_or_none()
        if not objection:
            return False
        await self.session.delete(objection)
        await self.session.flush()
        return True
