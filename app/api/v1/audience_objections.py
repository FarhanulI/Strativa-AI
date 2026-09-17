from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.database import get_db_session
from app.models.workspace_member import WorkspaceMember
from app.schemas.audience_objection import (
    AudienceObjectionCreate,
    AudienceObjectionResponse,
    AudienceObjectionUpdate,
)
from app.services.audience_objection import AudienceObjectionService

router = APIRouter(
    prefix="/audience-intelligence/{audience_id}/objections",
    tags=["Audience Objections"],
)


async def get_audience_objection_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AudienceObjectionService:
    return AudienceObjectionService(session)


@router.post("", response_model=AudienceObjectionResponse, status_code=status.HTTP_201_CREATED)
async def create_audience_objection(
    audience_id: UUID,
    payload: AudienceObjectionCreate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceObjectionService, Depends(get_audience_objection_service)],
) -> AudienceObjectionResponse:
    try:
        objection = await service.create(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_member.workspace_id,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            severity=payload.severity,
            frequency=payload.frequency,
        )
        return AudienceObjectionResponse.model_validate(objection)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[AudienceObjectionResponse])
async def list_audience_objections(
    audience_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceObjectionService, Depends(get_audience_objection_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[AudienceObjectionResponse]:
    try:
        objections = await service.list(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_member.workspace_id,
            skip=skip,
            limit=limit,
        )
        return [AudienceObjectionResponse.model_validate(o) for o in objections]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("/{objection_id}", response_model=AudienceObjectionResponse)
async def get_audience_objection(
    audience_id: UUID,
    objection_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceObjectionService, Depends(get_audience_objection_service)],
) -> AudienceObjectionResponse:
    try:
        objection = await service.get(
            audience_intelligence_id=audience_id,
            objection_id=objection_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not objection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objection not found",
            )
        return AudienceObjectionResponse.model_validate(objection)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.patch("/{objection_id}", response_model=AudienceObjectionResponse)
async def update_audience_objection(
    audience_id: UUID,
    objection_id: UUID,
    payload: AudienceObjectionUpdate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceObjectionService, Depends(get_audience_objection_service)],
) -> AudienceObjectionResponse:
    try:
        objection = await service.update(
            audience_intelligence_id=audience_id,
            objection_id=objection_id,
            workspace_id=workspace_member.workspace_id,
            title=payload.title,
            description=payload.description,
            evidence=payload.evidence,
            severity=payload.severity,
            frequency=payload.frequency,
        )
        if not objection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objection not found",
            )
        return AudienceObjectionResponse.model_validate(objection)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.delete("/{objection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audience_objection(
    audience_id: UUID,
    objection_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceObjectionService, Depends(get_audience_objection_service)],
) -> None:
    try:
        success = await service.delete(
            audience_intelligence_id=audience_id,
            objection_id=objection_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objection not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e
