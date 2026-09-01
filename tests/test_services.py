from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace
from app.services.business_context import BusinessContextService
from app.services.service import ServiceService


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
        name="ABC Consulting",
        topics=["consulting", "business"],
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
        commercial_objectives=["increase_revenue"],
    )
    return context


@pytest.mark.asyncio
async def test_create_service(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test creating a service"""
    service = ServiceService(db_session)
    result = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Business Consulting",
        description="Professional business consulting services",
        category="Consulting",
        price=200.00,
        currency="USD",
        features=["strategy", "implementation"],
        benefits=["revenue growth", "efficiency"],
        target_audience=["startups", "enterprises"],
    )
    assert result is not None
    assert result.name == "Business Consulting"
    assert result.price == 200.00


@pytest.mark.asyncio
async def test_list_services(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test listing services"""
    service = ServiceService(db_session)

    # Create multiple services
    for i in range(2):
        await service.create(
            business_context_id=business_context_with_profile.id,
            workspace_id=business_profile.workspace_id,
            name=f"Service {i}",
        )

    services = await service.list(business_context_with_profile.id, business_profile.workspace_id)
    assert len(services) == 2


@pytest.mark.asyncio
async def test_get_service(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test getting a service by ID"""
    service = ServiceService(db_session)

    created = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Consulting",
    )

    retrieved = await service.get(
        created.id,
        business_context_with_profile.id,
        business_profile.workspace_id,
    )
    assert retrieved is not None
    assert retrieved.id == created.id


@pytest.mark.asyncio
async def test_update_service(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test updating a service"""
    service = ServiceService(db_session)

    created = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Consulting",
        price=100.00,
    )

    updated = await service.update(
        service_id=created.id,
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Premium Consulting",
        price=250.00,
    )
    assert updated is not None
    assert updated.name == "Premium Consulting"
    assert updated.price == 250.00


@pytest.mark.asyncio
async def test_delete_service(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test deleting a service"""
    service = ServiceService(db_session)

    created = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Consulting",
    )

    deleted = await service.delete(
        created.id,
        business_context_with_profile.id,
        business_profile.workspace_id,
    )
    assert deleted is True


@pytest.mark.asyncio
async def test_cross_workspace_service_access_returns_not_found(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test that cross-workspace service access returns not found"""
    service = ServiceService(db_session)

    created = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Consulting",
    )

    # Try to access with different workspace ID
    other_workspace_id = uuid4()
    result = await service.get(
        created.id,
        business_context_with_profile.id,
        other_workspace_id,
    )
    assert result is None
