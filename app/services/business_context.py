from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_context import BusinessContext
from app.repositories.business_context import BusinessContextRepository
from app.repositories.content_profile import ContentProfileRepository


class BusinessContextService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.business_context_repository = BusinessContextRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        commercial_objectives: dict[str, Any] | list[Any] | None = None,
        target_market: str | None = None,
        pricing_position: str | None = None,
    ) -> BusinessContext:
        """
        Create a new business context for a content profile.

        BusinessContext is optional and can be created for both creators and businesses.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")

        # Check if business context already exists
        existing_context = await self.business_context_repository.get_by_profile(profile_id)
        if existing_context:
            raise ValueError("Business context already exists for this content profile.")

        context = BusinessContext(
            content_profile_id=profile_id,
            commercial_objectives=commercial_objectives,
            target_market=target_market,
            pricing_position=pricing_position,
        )
        await self.business_context_repository.create(context)
        await self.session.commit()
        return context

    async def get(self, profile_id: UUID, workspace_id: UUID) -> BusinessContext | None:
        """
        Get a business context for a content profile within a workspace.

        Verify the profile belongs to the workspace to prevent cross-tenant access.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        return await self.business_context_repository.get_by_profile(profile_id)

    async def update(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        commercial_objectives: dict[str, Any] | list[Any] | None = None,
        target_market: str | None = None,
        pricing_position: str | None = None,
    ) -> BusinessContext | None:
        """Update a business context within a workspace"""
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        context = await self.business_context_repository.get_by_profile(profile_id)
        if not context:
            return None

        if commercial_objectives is not None:
            context.commercial_objectives = commercial_objectives
        if target_market is not None:
            context.target_market = target_market
        if pricing_position is not None:
            context.pricing_position = pricing_position

        await self.business_context_repository.update(context)
        await self.session.commit()
        return context

    async def delete(self, profile_id: UUID, workspace_id: UUID) -> bool:
        """Delete a business context within a workspace"""
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return False

        result = await self.business_context_repository.delete(profile_id)
        if result:
            await self.session.commit()
        return result
