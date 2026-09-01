from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_profile import ContentProfile


class ContentProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, profile: ContentProfile) -> ContentProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_by_id(self, profile_id: UUID, workspace_id: UUID) -> ContentProfile | None:
        stmt = select(ContentProfile).where(
            (ContentProfile.id == profile_id) & (ContentProfile.workspace_id == workspace_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ContentProfile]:
        stmt = (
            select(ContentProfile)
            .where(ContentProfile.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, profile: ContentProfile) -> ContentProfile:
        await self.session.merge(profile)
        await self.session.flush()
        return profile

    async def delete(self, profile_id: UUID, workspace_id: UUID) -> bool:
        profile = await self.get_by_id(profile_id, workspace_id)
        if not profile:
            return False
        await self.session.delete(profile)
        await self.session.flush()
        return True
