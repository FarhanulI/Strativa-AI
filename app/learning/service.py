from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import Learning
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.learning import LearningRepository


class LearningService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = LearningRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def _profile(self, profile_id: UUID, workspace_id: UUID):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    async def create(self, profile_id: UUID, workspace_id: UUID, **values: Any) -> Learning:
        await self._profile(profile_id, workspace_id)
        learning = Learning(profile_id=profile_id, **values)
        await self.repository.create(learning)
        await self.session.commit()
        return learning

    async def get(self, profile_id: UUID, workspace_id: UUID, learning_id: UUID) -> Learning | None:
        await self._profile(profile_id, workspace_id)
        return await self.repository.get_by_id(profile_id, learning_id)

    async def list(self, profile_id: UUID, workspace_id: UUID, **filters: Any) -> list[Learning]:
        await self._profile(profile_id, workspace_id)
        return await self.repository.list_by_profile(profile_id, **filters)

    async def update(
        self, profile_id: UUID, workspace_id: UUID, learning_id: UUID, **values: Any
    ) -> Learning | None:
        await self._profile(profile_id, workspace_id)
        learning = await self.repository.get_by_id(profile_id, learning_id)
        if not learning:
            return None
        for key, value in values.items():
            if value is not None:
                setattr(learning, key, value)
        await self.repository.update(learning)
        await self.session.commit()
        return learning

    async def delete(self, profile_id: UUID, workspace_id: UUID, learning_id: UUID) -> bool:
        await self._profile(profile_id, workspace_id)
        learning = await self.repository.get_by_id(profile_id, learning_id)
        if not learning:
            return False
        await self.repository.delete(learning)
        await self.session.commit()
        return True
