from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.repositories.business_context import BusinessContextRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.service import ServiceRepository


class ServiceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.service_repository = ServiceRepository(session)
        self.business_context_repository = BusinessContextRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        business_context_id: UUID,
        workspace_id: UUID,
        name: str,
        description: str | None = None,
        category: str | None = None,
        price: float | None = None,
        currency: str | None = None,
        features: dict[str, Any] | list[Any] | None = None,
        benefits: dict[str, Any] | list[Any] | None = None,
        target_audience: dict[str, Any] | list[Any] | None = None,
    ) -> Service:
        """Create a new service for a business context"""
        # Verify business context exists and belongs to workspace
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            raise ValueError("Business context not found")

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            raise ValueError("Business context not found in workspace")

        service = Service(
            business_context_id=business_context_id,
            name=name,
            description=description,
            category=category,
            price=price,
            currency=currency,
            features=features,
            benefits=benefits,
            target_audience=target_audience,
        )
        await self.service_repository.create(service)
        await self.session.commit()
        return service

    async def get(
        self,
        service_id: UUID,
        business_context_id: UUID,
        workspace_id: UUID,
    ) -> Service | None:
        """Get a service by ID within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return None

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return None

        service = await self.service_repository.get_by_id(service_id)
        if service and service.business_context_id == business_context_id:
            return service
        return None

    async def list(self, business_context_id: UUID, workspace_id: UUID) -> list[Service]:
        """List all services for a business context within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return []

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return []

        return await self.service_repository.list_by_business_context(business_context_id)

    async def update(
        self,
        service_id: UUID,
        business_context_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        price: float | None = None,
        currency: str | None = None,
        features: dict[str, Any] | list[Any] | None = None,
        benefits: dict[str, Any] | list[Any] | None = None,
        target_audience: dict[str, Any] | list[Any] | None = None,
    ) -> Service | None:
        """Update a service within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return None

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return None

        service = await self.service_repository.get_by_id(service_id)
        if not service or service.business_context_id != business_context_id:
            return None

        if name is not None:
            service.name = name
        if description is not None:
            service.description = description
        if category is not None:
            service.category = category
        if price is not None:
            service.price = price
        if currency is not None:
            service.currency = currency
        if features is not None:
            service.features = features
        if benefits is not None:
            service.benefits = benefits
        if target_audience is not None:
            service.target_audience = target_audience

        await self.service_repository.update(service)
        await self.session.commit()
        return service

    async def delete(self, service_id: UUID, business_context_id: UUID, workspace_id: UUID) -> bool:
        """Delete a service within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return False

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return False

        service = await self.service_repository.get_by_id(service_id)
        if not service or service.business_context_id != business_context_id:
            return False

        result = await self.service_repository.delete(service_id)
        if result:
            await self.session.commit()
        return result
