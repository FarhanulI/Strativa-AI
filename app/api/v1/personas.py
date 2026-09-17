from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.database import get_db_session
from app.models.workspace_member import WorkspaceMember
from app.schemas.persona import PersonaCreate, PersonaResponse, PersonaUpdate
from app.services.persona import PersonaService

router = APIRouter(
    prefix="/audience-intelligence/{audience_id}/personas",
    tags=["Personas"],
)


async def get_persona_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PersonaService:
    return PersonaService(session)


@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    audience_id: UUID,
    payload: PersonaCreate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[PersonaService, Depends(get_persona_service)],
) -> PersonaResponse:
    try:
        persona = await service.create(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_member.workspace_id,
            name=payload.name,
            description=payload.description,
            demographics=payload.demographics,
            psychographics=payload.psychographics,
            goals=payload.goals,
            pain_points=payload.pain_points,
            desires=payload.desires,
            behaviors=payload.behaviors,
            content_preferences=payload.content_preferences,
        )
        return PersonaResponse.model_validate(persona)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[PersonaResponse])
async def list_personas(
    audience_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[PersonaService, Depends(get_persona_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[PersonaResponse]:
    try:
        personas = await service.list(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_member.workspace_id,
            skip=skip,
            limit=limit,
        )
        return [PersonaResponse.model_validate(p) for p in personas]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    audience_id: UUID,
    persona_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[PersonaService, Depends(get_persona_service)],
) -> PersonaResponse:
    try:
        persona = await service.get(
            audience_intelligence_id=audience_id,
            persona_id=persona_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )
        return PersonaResponse.model_validate(persona)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    audience_id: UUID,
    persona_id: UUID,
    payload: PersonaUpdate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[PersonaService, Depends(get_persona_service)],
) -> PersonaResponse:
    try:
        persona = await service.update(
            audience_intelligence_id=audience_id,
            persona_id=persona_id,
            workspace_id=workspace_member.workspace_id,
            name=payload.name,
            description=payload.description,
            demographics=payload.demographics,
            psychographics=payload.psychographics,
            goals=payload.goals,
            pain_points=payload.pain_points,
            desires=payload.desires,
            behaviors=payload.behaviors,
            content_preferences=payload.content_preferences,
        )
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )
        return PersonaResponse.model_validate(persona)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    audience_id: UUID,
    persona_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[PersonaService, Depends(get_persona_service)],
) -> None:
    try:
        success = await service.delete(
            audience_intelligence_id=audience_id,
            persona_id=persona_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e
