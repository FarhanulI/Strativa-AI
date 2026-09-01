from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, service: Service) -> Service:
        """Create a new service"""
        self.session.add(service)
        await self.session.flush()
        return service

    async def get_by_id(self, service_id: UUID) -> Service | None:
        """Get a service by ID"""
        stmt = select(Service).where(Service.id == service_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_business_context(self, business_context_id: UUID) -> list[Service]:
        """List all services for a business context"""
        stmt = select(Service).where(Service.business_context_id == business_context_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, service: Service) -> Service:
        """Update a service"""
        await self.session.merge(service)
        await self.session.flush()
        return service

    async def delete(self, service_id: UUID) -> bool:
        """Delete a service by ID"""
        stmt = select(Service).where(Service.id == service_id)
        result = await self.session.execute(stmt)
        service = result.scalar_one_or_none()
        if service:
            await self.session.delete(service)
            await self.session.flush()
            return True
        return False
