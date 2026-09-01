from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_context import BusinessContext
from app.models.content_profile import ContentProfile, ContentProfileType
from app.models.workspace import Workspace
from app.services.business_context import BusinessContextService


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
async def creator_profile(db_session: AsyncSession, workspace: Workspace) -> ContentProfile:
    """Create a test creator content profile"""
    profile = ContentProfile(
        workspace_id=workspace.id,
        type=ContentProfileType.CREATOR,
        name="Test Creator",
        positioning="Funny and relatable content",
        topics=["comedy", "memes"],
        goals=["audience_growth"],
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


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


@pytest.mark.asyncio
async def test_create_business_context_for_creator(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test that creators can have business context"""
    service = BusinessContextService(db_session)
    context = await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
        target_market="Football enthusiasts",
        pricing_position="Premium",
    )
    assert context is not None
    assert context.content_profile_id == creator_profile.id
    assert context.commercial_objectives == ["course_sales"]
    assert context.target_market == "Football enthusiasts"


@pytest.mark.asyncio
async def test_create_business_context_for_business(
    db_session: AsyncSession,
    business_profile: ContentProfile,
):
    """Test that businesses can have business context"""
    service = BusinessContextService(db_session)
    context = await service.create(
        profile_id=business_profile.id,
        workspace_id=business_profile.workspace_id,
        commercial_objectives=["increase_sales", "increase_repeat_purchase"],
        target_market="Young football players in Bangladesh",
        pricing_position="Affordable premium",
    )
    assert context is not None
    assert context.content_profile_id == business_profile.id


@pytest.mark.asyncio
async def test_duplicate_business_context_returns_error(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test that creating duplicate business context returns 409"""
    service = BusinessContextService(db_session)

    # Create first context
    await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
    )

    # Try to create another context for same profile
    with pytest.raises(ValueError) as exc_info:
        await service.create(
            profile_id=creator_profile.id,
            workspace_id=creator_profile.workspace_id,
            commercial_objectives=["course_sales"],
        )
    assert "already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_business_context(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test retrieving business context"""
    service = BusinessContextService(db_session)
    created = await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
    )

    retrieved = await service.get(creator_profile.id, creator_profile.workspace_id)
    assert retrieved is not None
    assert retrieved.id == created.id


@pytest.mark.asyncio
async def test_update_business_context(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test updating business context"""
    service = BusinessContextService(db_session)
    await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
    )

    updated = await service.update(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        target_market="New market",
        pricing_position="Budget-friendly",
    )
    assert updated is not None
    assert updated.target_market == "New market"
    assert updated.pricing_position == "Budget-friendly"


@pytest.mark.asyncio
async def test_delete_business_context(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test deleting business context"""
    service = BusinessContextService(db_session)
    await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
    )

    deleted = await service.delete(creator_profile.id, creator_profile.workspace_id)
    assert deleted is True

    retrieved = await service.get(creator_profile.id, creator_profile.workspace_id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_creator_without_business_context_is_valid(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test that creators can exist without business context"""
    # Verify the creator profile exists
    assert creator_profile.id is not None
    assert creator_profile.type == ContentProfileType.CREATOR
    assert creator_profile.business_context is None


@pytest.mark.asyncio
async def test_cross_workspace_access_returns_not_found(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test that cross-workspace access returns not found"""
    service = BusinessContextService(db_session)

    # Create context in one workspace
    await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
    )

    # Try to access with different workspace ID
    other_workspace_id = uuid4()
    result = await service.get(creator_profile.id, other_workspace_id)
    assert result is None


@pytest.mark.asyncio
async def test_cascade_delete_business_context_with_profile(
    db_session: AsyncSession,
    creator_profile: ContentProfile,
):
    """Test that deleting content profile cascades to business context"""
    service = BusinessContextService(db_session)

    # Create business context
    context = await service.create(
        profile_id=creator_profile.id,
        workspace_id=creator_profile.workspace_id,
        commercial_objectives=["course_sales"],
    )
    context_id = context.id

    # Delete the profile
    await db_session.delete(creator_profile)
    await db_session.commit()

    # Verify context is also deleted
    context_check = await db_session.get(BusinessContext, context_id)
    assert context_check is None
