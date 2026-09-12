from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_draft import ContentDraft
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.workspace import WorkspaceRepository


class ContentLibraryService:
    def __init__(self, session: AsyncSession):
        self.repository = ContentDraftRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.workspace_repository = WorkspaceRepository(session)

    async def list_library(
        self,
        workspace_id: UUID,
        profile_id: UUID | None = None,
        status: str | None = None,
        platform: str | None = None,
        format: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContentDraft]:
        await self._verify_workspace(workspace_id)
        if profile_id is not None:
            await self._verify_profile(profile_id, workspace_id)
        return await self.repository.list_library(
            workspace_id=workspace_id,
            profile_id=profile_id,
            status=status,
            platform=platform,
            format=format,
            created_after=created_after,
            created_before=created_before,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=limit,
        )

    async def get_library_item(self, draft_id: UUID, workspace_id: UUID) -> ContentDraft:
        await self._verify_workspace(workspace_id)
        draft = await self.repository.get_with_lineage(draft_id, workspace_id)
        if not draft:
            raise ValueError("Content draft not found")
        return draft

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    async def _verify_workspace(self, workspace_id: UUID):
        workspace = await self.workspace_repository.get_by_id(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        return workspace
