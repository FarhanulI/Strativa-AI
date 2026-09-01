from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_intelligence import Persona


class PersonaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, persona: Persona) -> Persona:
        self.session.add(persona)
        await self.session.flush()
        return persona

    async def get_by_id(self, persona_id: UUID) -> Persona | None:
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_audience(
        self, audience_intelligence_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Persona]:
        stmt = (
            select(Persona)
            .where(Persona.audience_intelligence_id == audience_intelligence_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, persona: Persona) -> Persona:
        await self.session.merge(persona)
        await self.session.flush()
        return persona

    async def delete(self, persona_id: UUID) -> bool:
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.session.execute(stmt)
        persona = result.scalar_one_or_none()
        if not persona:
            return False
        await self.session.delete(persona)
        await self.session.flush()
        return True
