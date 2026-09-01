from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_context import BusinessContext


class BusinessContextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, business_context: BusinessContext) -> BusinessContext:
        """Create a new business context"""
        self.session.add(business_context)
        await self.session.flush()
        return business_context

    async def get_by_profile(self, profile_id: UUID) -> BusinessContext | None:
        """Get a business context by content profile ID"""
        stmt = select(BusinessContext).where(BusinessContext.content_profile_id == profile_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, context_id: UUID) -> BusinessContext | None:
        """Get a business context by ID"""
        stmt = select(BusinessContext).where(BusinessContext.id == context_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, business_context: BusinessContext) -> BusinessContext:
        """Update a business context"""
        await self.session.merge(business_context)
        await self.session.flush()
        return business_context

    async def delete(self, profile_id: UUID) -> bool:
        """Delete a business context by content profile ID"""
        stmt = select(BusinessContext).where(BusinessContext.content_profile_id == profile_id)
        result = await self.session.execute(stmt)
        context = result.scalar_one_or_none()
        if context:
            await self.session.delete(context)
            await self.session.flush()
            return True
        return False
