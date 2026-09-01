from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.offer import Offer


class OfferRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, offer: Offer) -> Offer:
        """Create a new offer"""
        self.session.add(offer)
        await self.session.flush()
        return offer

    async def get_by_id(self, offer_id: UUID) -> Offer | None:
        """Get an offer by ID"""
        stmt = select(Offer).where(Offer.id == offer_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_business_context(self, business_context_id: UUID) -> list[Offer]:
        """List all offers for a business context"""
        stmt = select(Offer).where(Offer.business_context_id == business_context_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, offer: Offer) -> Offer:
        """Update an offer"""
        await self.session.merge(offer)
        await self.session.flush()
        return offer

    async def delete(self, offer_id: UUID) -> bool:
        """Delete an offer by ID"""
        stmt = select(Offer).where(Offer.id == offer_id)
        result = await self.session.execute(stmt)
        offer = result.scalar_one_or_none()
        if offer:
            await self.session.delete(offer)
            await self.session.flush()
            return True
        return False
