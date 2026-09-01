from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.workspace import WorkspaceRepository


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = WorkspaceRepository(session)

    async def create(self, name: str, slug: str) -> Workspace:
        """Create a new workspace"""
        workspace = Workspace(name=name, slug=slug)
        try:
            await self.repository.create(workspace)
            await self.session.commit()
            return workspace
        except IntegrityError as err:
            await self.session.rollback()
            raise ValueError(f"Workspace with slug '{slug}' already exists") from err

    async def get(self, workspace_id: UUID) -> Workspace | None:
        """Get a workspace by ID"""
        return await self.repository.get_by_id(workspace_id)

    async def list(self, skip: int = 0, limit: int = 100) -> list[Workspace]:
        """List all workspaces with pagination"""
        return await self.repository.list_all(skip=skip, limit=limit)

    async def update(
        self, workspace_id: UUID, name: str | None, slug: str | None
    ) -> Workspace | None:
        """Update a workspace"""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            return None

        if name is not None:
            workspace.name = name
        if slug is not None:
            workspace.slug = slug

        try:
            await self.repository.update(workspace)
            await self.session.commit()
            return workspace
        except IntegrityError as err:
            await self.session.rollback()
            raise ValueError(f"Workspace with slug '{slug}' already exists") from err

    async def delete(self, workspace_id: UUID) -> bool:
        """Delete a workspace"""
        success = await self.repository.delete(workspace_id)
        if success:
            await self.session.commit()
        return success
