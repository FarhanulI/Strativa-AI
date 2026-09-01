from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, product: Product) -> Product:
        """Create a new product"""
        self.session.add(product)
        await self.session.flush()
        return product

    async def get_by_id(self, product_id: UUID) -> Product | None:
        """Get a product by ID"""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_business_context(self, business_context_id: UUID) -> list[Product]:
        """List all products for a business context"""
        stmt = select(Product).where(Product.business_context_id == business_context_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, product: Product) -> Product:
        """Update a product"""
        await self.session.merge(product)
        await self.session.flush()
        return product

    async def delete(self, product_id: UUID) -> bool:
        """Delete a product by ID"""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            await self.session.delete(product)
            await self.session.flush()
            return True
        return False
