from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import AudienceIntelligence


class AudienceIntelligenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, audience_intelligence: AudienceIntelligence) -> AudienceIntelligence:
        self.session.add(audience_intelligence)
        await self.session.flush()
        return audience_intelligence

    async def get_by_profile(self, content_profile_id: UUID) -> AudienceIntelligence | None:
        stmt = select(AudienceIntelligence).where(
            AudienceIntelligence.content_profile_id == content_profile_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, audience_intelligence: AudienceIntelligence) -> AudienceIntelligence:
        await self.session.merge(audience_intelligence)
        await self.session.flush()
        return audience_intelligence

    async def delete(self, audience_intelligence_id: UUID) -> bool:
        stmt = select(AudienceIntelligence).where(
            AudienceIntelligence.id == audience_intelligence_id
        )
        result = await self.session.execute(stmt)
        audience_intelligence = result.scalar_one_or_none()
        if not audience_intelligence:
            return False
        await self.session.delete(audience_intelligence)
        await self.session.flush()
        return True
