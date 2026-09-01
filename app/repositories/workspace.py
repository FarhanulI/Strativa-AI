from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, workspace: Workspace) -> Workspace:
        """Create a new workspace"""
        self.session.add(workspace)
        await self.session.flush()
        return workspace

    async def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        """Get a workspace by ID"""
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Workspace | None:
        """Get a workspace by slug"""
        stmt = select(Workspace).where(Workspace.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Workspace]:
        """List all workspaces with pagination"""
        stmt = select(Workspace).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, workspace: Workspace) -> Workspace:
        """Update a workspace"""
        await self.session.merge(workspace)
        await self.session.flush()
        return workspace

    async def delete(self, workspace_id: UUID) -> bool:
        """Delete a workspace"""
        workspace = await self.get_by_id(workspace_id)
        if not workspace:
            return False
        await self.session.delete(workspace)
        await self.session.flush()
        return True
