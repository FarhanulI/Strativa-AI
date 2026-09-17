from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.database import get_db_session
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate
from app.services.workspace import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


async def get_workspace_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceService:
    return WorkspaceService(session)


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Create a new workspace"""
    try:
        workspace = await service.create(name=payload.name, slug=payload.slug)
        return WorkspaceResponse.model_validate(workspace)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Get a workspace by ID"""
    workspace = await service.get(workspace_member.workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return WorkspaceResponse.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    payload: WorkspaceUpdate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Update a workspace"""
    try:
        workspace = await service.update(
            workspace_id=workspace_member.workspace_id,
            name=payload.name,
            slug=payload.slug,
        )
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return WorkspaceResponse.model_validate(workspace)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Delete a workspace"""
    success = await service.delete(workspace_member.workspace_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
