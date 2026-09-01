from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand


class BrandRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, brand: Brand) -> Brand:
        """Create a new brand"""
        self.session.add(brand)
        await self.session.flush()
        return brand

    async def get_by_profile(self, profile_id: UUID) -> Brand | None:
        """Get a brand by content profile ID"""
        stmt = select(Brand).where(Brand.content_profile_id == profile_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, brand: Brand) -> Brand:
        """Update a brand"""
        await self.session.merge(brand)
        await self.session.flush()
        return brand

    async def delete(self, profile_id: UUID) -> bool:
        """Delete a brand by content profile ID"""
        stmt = select(Brand).where(Brand.content_profile_id == profile_id)
        result = await self.session.execute(stmt)
        brand = result.scalar_one_or_none()
        if brand:
            await self.session.delete(brand)
            await self.session.flush()
            return True
        return False
