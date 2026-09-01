from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace
from app.services.business_context import BusinessContextService
from app.services.offer import OfferService


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
        topics=["sports", "promotions"],
        goals=["sales"],
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
async def test_create_offer(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test creating an offer"""
    service = OfferService(db_session)

    now = datetime.now()
    offer = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Summer Sale",
        description="50% off on all items",
        offer_type="discount",
        value=50.00,
        currency="USD",
        starts_at=now,
        ends_at=now + timedelta(days=30),
        active=True,
        terms={"conditions": "limited time"},
        target_audience=["premium members"],
    )
    assert offer is not None
    assert offer.name == "Summer Sale"
    assert offer.active is True


@pytest.mark.asyncio
async def test_list_offers(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test listing offers"""
    service = OfferService(db_session)

    # Create multiple offers
    for i in range(2):
        await service.create(
            business_context_id=business_context_with_profile.id,
            workspace_id=business_profile.workspace_id,
            name=f"Offer {i}",
        )

    offers = await service.list(business_context_with_profile.id, business_profile.workspace_id)
    assert len(offers) == 2


@pytest.mark.asyncio
async def test_get_offer(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test getting an offer by ID"""
    service = OfferService(db_session)

    created = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Summer Sale",
    )

    retrieved = await service.get(
        created.id,
        business_context_with_profile.id,
        business_profile.workspace_id,
    )
    assert retrieved is not None
    assert retrieved.id == created.id


@pytest.mark.asyncio
async def test_update_offer(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test updating an offer"""
    service = OfferService(db_session)

    offer = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Summer Sale",
        active=True,
    )

    updated = await service.update(
        offer_id=offer.id,
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Winter Sale",
        active=False,
    )
    assert updated is not None
    assert updated.name == "Winter Sale"
    assert updated.active is False


@pytest.mark.asyncio
async def test_delete_offer(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test deleting an offer"""
    service = OfferService(db_session)

    offer = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Summer Sale",
    )

    deleted = await service.delete(
        offer.id,
        business_context_with_profile.id,
        business_profile.workspace_id,
    )
    assert deleted is True


@pytest.mark.asyncio
async def test_offer_start_end_dates(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test offer start/end dates validation"""
    service = OfferService(db_session)

    now = datetime.now()

    # Valid: starts before ends
    offer = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Valid Offer",
        starts_at=now,
        ends_at=now + timedelta(days=30),
    )
    assert offer is not None


@pytest.mark.asyncio
async def test_offer_invalid_date_range(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test that invalid date range raises error"""
    service = OfferService(db_session)

    now = datetime.now()

    # Invalid: starts after ends
    with pytest.raises(ValueError) as exc_info:
        await service.create(
            business_context_id=business_context_with_profile.id,
            workspace_id=business_profile.workspace_id,
            name="Invalid Offer",
            starts_at=now + timedelta(days=30),
            ends_at=now,
        )
    assert "must not be after" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cross_workspace_offer_access_returns_not_found(
    db_session: AsyncSession,
    business_profile: ContentProfile,
    business_context_with_profile,
):
    """Test that cross-workspace offer access returns not found"""
    service = OfferService(db_session)

    offer = await service.create(
        business_context_id=business_context_with_profile.id,
        workspace_id=business_profile.workspace_id,
        name="Summer Sale",
    )

    # Try to access with different workspace ID
    other_workspace_id = uuid4()
    result = await service.get(
        offer.id,
        business_context_with_profile.id,
        other_workspace_id,
    )
    assert result is None
