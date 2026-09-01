from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_profile import ContentProfile, ContentProfileType
from app.repositories.content_profile import ContentProfileRepository


class ContentProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ContentProfileRepository(session)

    async def create(
        self,
        workspace_id: UUID,
        type: ContentProfileType,
        name: str,
        description: str | None = None,
        website: str | None = None,
        location: str | None = None,
        positioning: str | None = None,
        topics: list[str] | None = None,
        expertise: list[str] | None = None,
        goals: list[str] | None = None,
    ) -> ContentProfile:
        validated_type = self._validate_type(type)
        profile = ContentProfile(
            workspace_id=workspace_id,
            type=validated_type,
            name=name,
            description=description,
            website=website,
            location=location,
            positioning=positioning,
            topics=topics,
            expertise=expertise,
            goals=goals,
        )
        await self.repository.create(profile)
        await self.session.commit()
        return profile

    async def get(self, profile_id: UUID, workspace_id: UUID) -> ContentProfile | None:
        return await self.repository.get_by_id(profile_id, workspace_id)

    async def list(
        self, workspace_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ContentProfile]:
        return await self.repository.list_by_workspace(
            workspace_id=workspace_id, skip=skip, limit=limit
        )

    async def update(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        type: ContentProfileType | None = None,
        name: str | None = None,
        description: str | None = None,
        website: str | None = None,
        location: str | None = None,
        positioning: str | None = None,
        topics: list[str] | None = None,
        expertise: list[str] | None = None,
        goals: list[str] | None = None,
    ) -> ContentProfile | None:
        profile = await self.repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        if type is not None:
            profile.type = self._validate_type(type)
        if name is not None:
            profile.name = name
        if description is not None:
            profile.description = description
        if website is not None:
            profile.website = website
        if location is not None:
            profile.location = location
        if positioning is not None:
            profile.positioning = positioning
        if topics is not None:
            profile.topics = topics
        if expertise is not None:
            profile.expertise = expertise
        if goals is not None:
            profile.goals = goals

        await self.repository.update(profile)
        await self.session.commit()
        return profile

    async def delete(self, profile_id: UUID, workspace_id: UUID) -> bool:
        success = await self.repository.delete(profile_id, workspace_id)
        if success:
            await self.session.commit()
        return success

    @staticmethod
    def _validate_type(profile_type: ContentProfileType | str) -> ContentProfileType:
        if isinstance(profile_type, ContentProfileType):
            return profile_type
        return ContentProfileType(profile_type)
