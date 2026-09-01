from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.offer import Offer
from app.repositories.business_context import BusinessContextRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.offer import OfferRepository


class OfferService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.offer_repository = OfferRepository(session)
        self.business_context_repository = BusinessContextRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        business_context_id: UUID,
        workspace_id: UUID,
        name: str,
        description: str | None = None,
        offer_type: str | None = None,
        value: float | None = None,
        currency: str | None = None,
        terms: dict[str, Any] | None = None,
        target_audience: dict[str, Any] | list[Any] | None = None,
        starts_at: Any = None,
        ends_at: Any = None,
        active: bool = True,
    ) -> Offer:
        """Create a new offer for a business context"""
        # Verify business context exists and belongs to workspace
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            raise ValueError("Business context not found")

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            raise ValueError("Business context not found in workspace")

        # Validate start/end dates if provided
        if starts_at is not None and ends_at is not None:
            if starts_at > ends_at:
                raise ValueError("starts_at must not be after ends_at")

        offer = Offer(
            business_context_id=business_context_id,
            name=name,
            description=description,
            offer_type=offer_type,
            value=value,
            currency=currency,
            terms=terms,
            target_audience=target_audience,
            starts_at=starts_at,
            ends_at=ends_at,
            active=active,
        )
        await self.offer_repository.create(offer)
        await self.session.commit()
        return offer

    async def get(
        self,
        offer_id: UUID,
        business_context_id: UUID,
        workspace_id: UUID,
    ) -> Offer | None:
        """Get an offer by ID within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return None

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return None

        offer = await self.offer_repository.get_by_id(offer_id)
        if offer and offer.business_context_id == business_context_id:
            return offer
        return None

    async def list(self, business_context_id: UUID, workspace_id: UUID) -> list[Offer]:
        """List all offers for a business context within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return []

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return []

        return await self.offer_repository.list_by_business_context(business_context_id)

    async def update(
        self,
        offer_id: UUID,
        business_context_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        description: str | None = None,
        offer_type: str | None = None,
        value: float | None = None,
        currency: str | None = None,
        terms: dict[str, Any] | None = None,
        target_audience: dict[str, Any] | list[Any] | None = None,
        starts_at: Any = None,
        ends_at: Any = None,
        active: bool | None = None,
    ) -> Offer | None:
        """Update an offer within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return None

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return None

        offer = await self.offer_repository.get_by_id(offer_id)
        if not offer or offer.business_context_id != business_context_id:
            return None

        # Validate start/end dates if provided
        new_starts_at = starts_at if starts_at is not None else offer.starts_at
        new_ends_at = ends_at if ends_at is not None else offer.ends_at
        if new_starts_at is not None and new_ends_at is not None:
            if new_starts_at > new_ends_at:
                raise ValueError("starts_at must not be after ends_at")

        if name is not None:
            offer.name = name
        if description is not None:
            offer.description = description
        if offer_type is not None:
            offer.offer_type = offer_type
        if value is not None:
            offer.value = value
        if currency is not None:
            offer.currency = currency
        if terms is not None:
            offer.terms = terms
        if target_audience is not None:
            offer.target_audience = target_audience
        if starts_at is not None:
            offer.starts_at = starts_at
        if ends_at is not None:
            offer.ends_at = ends_at
        if active is not None:
            offer.active = active

        await self.offer_repository.update(offer)
        await self.session.commit()
        return offer

    async def delete(self, offer_id: UUID, business_context_id: UUID, workspace_id: UUID) -> bool:
        """Delete an offer within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return False

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return False

        offer = await self.offer_repository.get_by_id(offer_id)
        if not offer or offer.business_context_id != business_context_id:
            return False

        result = await self.offer_repository.delete(offer_id)
        if result:
            await self.session.commit()
        return result
