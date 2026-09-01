from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.repositories.business_context import BusinessContextRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.product import ProductRepository


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.product_repository = ProductRepository(session)
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
    ) -> Product:
        """Create a new product for a business context"""
        # Verify business context exists and belongs to workspace
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            raise ValueError("Business context not found")

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            raise ValueError("Business context not found in workspace")

        product = Product(
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
        await self.product_repository.create(product)
        await self.session.commit()
        return product

    async def get(
        self,
        product_id: UUID,
        business_context_id: UUID,
        workspace_id: UUID,
    ) -> Product | None:
        """Get a product by ID within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return None

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return None

        product = await self.product_repository.get_by_id(product_id)
        if product and product.business_context_id == business_context_id:
            return product
        return None

    async def list(self, business_context_id: UUID, workspace_id: UUID) -> list[Product]:
        """List all products for a business context within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return []

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return []

        return await self.product_repository.list_by_business_context(business_context_id)

    async def update(
        self,
        product_id: UUID,
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
    ) -> Product | None:
        """Update a product within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return None

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return None

        product = await self.product_repository.get_by_id(product_id)
        if not product or product.business_context_id != business_context_id:
            return None

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if category is not None:
            product.category = category
        if price is not None:
            product.price = price
        if currency is not None:
            product.currency = currency
        if features is not None:
            product.features = features
        if benefits is not None:
            product.benefits = benefits
        if target_audience is not None:
            product.target_audience = target_audience

        await self.product_repository.update(product)
        await self.session.commit()
        return product

    async def delete(self, product_id: UUID, business_context_id: UUID, workspace_id: UUID) -> bool:
        """Delete a product within a workspace"""
        context = await self.business_context_repository.get_by_id(business_context_id)
        if not context:
            return False

        profile = await self.profile_repository.get_by_id(context.content_profile_id, workspace_id)
        if not profile:
            return False

        product = await self.product_repository.get_by_id(product_id)
        if not product or product.business_context_id != business_context_id:
            return False

        result = await self.product_repository.delete(product_id)
        if result:
            await self.session.commit()
        return result
