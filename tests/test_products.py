from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace
from app.services.business_context import BusinessContextService
from app.services.product import ProductService


@pytest.fixture
async def workspace(db_session: AsyncSession) -> Workspace:
    """Create a test workspace"""
    workspace = Workspace(
        name="Test Workspace",
        slug="test-workspace",
    )
    db_session.add(workspace)
    await db_session.flush()
    return workspace


@pytest.fixture
async def business_profile(db_session: AsyncSession, workspace: Workspace) -> ContentProfile:
    """Create a test business content profile"""
    profile = ContentProfile(
        workspace_id=workspace.id,
        type=ContentProfileType.BUSINESS,
        name="ABC Sports",
        topics=["sportswear", "football"],
        goals=["brand_awareness", "sales"],
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


@pytest.fixture
async def business_context_with_profile(
    db_session: AsyncSession,
    business_profile: ContentProfile,
):
    """Create a business context for testing"""
    service = BusinessContextService(db_session)
    context = await service.create(
        profile_id=business_profile.id,
        workspace_id=business_profile.workspace_id,
        commercial_objectives=["increase_sales"],
    )
    return context


@pytest.mark.asyncio
async def test_create_product(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test creating a product"""
    service = ProductService(db_session)
    product = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Football Cleats",
        description="Professional football cleats",
        category="Footwear",
        price=150.00,
        currency="USD",
        features=["lightweight", "durable"],
        benefits=["better traction", "comfort"],
        target_audience=["professional players"],
    )
    assert product is not None
    assert product.name == "Football Cleats"
    assert product.price == 150.00


@pytest.mark.asyncio
async def test_list_products(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test listing products"""
    service = ProductService(db_session)

    # Create multiple products
    for i in range(3):
        await service.create(
            business_context_id=business_context_with_profile.id,
            workspace_id=business_profile.workspace_id,
            name=f"Product {i}",
        )

    products = await service.list(business_context_with_profile.id, business_profile.workspace_id)
    assert len(products) == 3


@pytest.mark.asyncio
async def test_get_product(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test getting a product by ID"""
    service = ProductService(db_session)

    created = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Football",
    )

    retrieved = await service.get(
        created.id,
        business_context_with_profile.id,
        business_profile.workspace_id,
    )
    assert retrieved is not None
    assert retrieved.id == created.id


@pytest.mark.asyncio
async def test_update_product(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test updating a product"""
    service = ProductService(db_session)

    product = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Football",
        price=50.00,
    )

    updated = await service.update(
        product_id=product.id,
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Premium Football",
        price=75.00,
    )
    assert updated is not None
    assert updated.name == "Premium Football"
    assert updated.price == 75.00


@pytest.mark.asyncio
async def test_delete_product(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test deleting a product"""
    service = ProductService(db_session)

    product = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Football",
    )

    deleted = await service.delete(
        product.id,
        business_context_with_profile.id,
        business_profile.workspace_id,
    )
    assert deleted is True


@pytest.mark.asyncio
async def test_cross_workspace_product_access_returns_not_found(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test that cross-workspace product access returns not found"""
    service = ProductService(db_session)

    product = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Football",
    )

    # Try to access with different workspace ID
    other_workspace_id = uuid4()
    result = await service.get(
        product.id,
        business_context_with_profile.id,
        other_workspace_id,
    )
    assert result is None


@pytest.mark.asyncio
async def test_invalid_business_context_product_access(
    db_session: AsyncSession,
    business_profile: ContentProfile,
):
    """Test that accessing product with invalid business context returns not found"""
    service = ProductService(db_session)

    invalid_context_id = uuid4()
    result = await service.list(invalid_context_id, business_profile.workspace_id)
    assert result == []
