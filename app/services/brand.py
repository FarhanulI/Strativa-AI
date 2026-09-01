from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.repositories.brand import BrandRepository
from app.repositories.content_profile import ContentProfileRepository


class BrandService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.brand_repository = BrandRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        positioning: str | None = None,
        mission: str | None = None,
        vision: str | None = None,
        unique_selling_proposition: str | None = None,
        values: dict[str, Any] | None = None,
        personality: dict[str, Any] | None = None,
        voice: dict[str, Any] | None = None,
        tone: dict[str, Any] | None = None,
        messaging_guidelines: dict[str, Any] | None = None,
        visual_identity: dict[str, Any] | None = None,
    ) -> Brand:
        """
        Create a new brand profile for a content profile.

        Brand is scoped through ContentProfile rather than duplicating workspace_id.
        This keeps ContentProfile as the ownership boundary and avoids inconsistent
        workspace relationships.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")

        # Check if brand already exists
        existing_brand = await self.brand_repository.get_by_profile(profile_id)
        if existing_brand:
            raise ValueError("Brand profile already exists for this content profile.")

        brand = Brand(
            content_profile_id=profile_id,
            positioning=positioning,
            mission=mission,
            vision=vision,
            unique_selling_proposition=unique_selling_proposition,
            values=values,
            personality=personality,
            voice=voice,
            tone=tone,
            messaging_guidelines=messaging_guidelines,
            visual_identity=visual_identity,
        )
        await self.brand_repository.create(brand)
        await self.session.commit()
        return brand

    async def get(self, profile_id: UUID, workspace_id: UUID) -> Brand | None:
        """
        Get a brand profile for a content profile within a specific workspace.

        Verify the profile belongs to the workspace to prevent cross-tenant access.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        return await self.brand_repository.get_by_profile(profile_id)

    async def update(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        positioning: str | None = None,
        mission: str | None = None,
        vision: str | None = None,
        unique_selling_proposition: str | None = None,
        values: dict[str, Any] | None = None,
        personality: dict[str, Any] | None = None,
        voice: dict[str, Any] | None = None,
        tone: dict[str, Any] | None = None,
        messaging_guidelines: dict[str, Any] | None = None,
        visual_identity: dict[str, Any] | None = None,
    ) -> Brand | None:
        """Update a brand profile within a workspace"""
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        brand = await self.brand_repository.get_by_profile(profile_id)
        if not brand:
            return None

        if positioning is not None:
            brand.positioning = positioning
        if mission is not None:
            brand.mission = mission
        if vision is not None:
            brand.vision = vision
        if unique_selling_proposition is not None:
            brand.unique_selling_proposition = unique_selling_proposition
        if values is not None:
            brand.values = values
        if personality is not None:
            brand.personality = personality
        if voice is not None:
            brand.voice = voice
        if tone is not None:
            brand.tone = tone
        if messaging_guidelines is not None:
            brand.messaging_guidelines = messaging_guidelines
        if visual_identity is not None:
            brand.visual_identity = visual_identity

        await self.brand_repository.update(brand)
        await self.session.commit()
        return brand

    async def delete(self, profile_id: UUID, workspace_id: UUID) -> bool:
        """Delete a brand profile within a workspace"""
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return False

        success = await self.brand_repository.delete(profile_id)
        if success:
            await self.session.commit()
        return success
