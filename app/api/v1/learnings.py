from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.learning.service import LearningService
from app.models.content_profile import ContentProfile
from app.schemas.learning import LearningCreate, LearningResponse, LearningUpdate

router = APIRouter(prefix="/profiles/{profile_id}", tags=["Learning Engine"])


def not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


async def get_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningService:
    return LearningService(session)


@router.post("/learnings", response_model=LearningResponse, status_code=201)
async def create(
    payload: LearningCreate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[LearningService, Depends(get_service)],
):
    try:
        return await service.create(profile.id, profile.workspace_id, **payload.model_dump())
    except ValueError as error:
        raise not_found(error) from error


@router.get("/learnings", response_model=list[LearningResponse])
async def list_learnings(
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[LearningService, Depends(get_service)],
    status: str | None = None,
    dimension: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    try:
        return await service.list(
            profile.id,
            profile.workspace_id,
            status=status,
            dimension=dimension,
            skip=skip,
            limit=limit,
        )
    except ValueError as error:
        raise not_found(error) from error


@router.get("/learnings/{learning_id}", response_model=LearningResponse)
async def get(
    learning_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[LearningService, Depends(get_service)],
):
    try:
        result = await service.get(profile.id, profile.workspace_id, learning_id)
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Learning not found")
    return result


@router.patch("/learnings/{learning_id}", response_model=LearningResponse)
async def update(
    learning_id: UUID,
    payload: LearningUpdate,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[LearningService, Depends(get_service)],
):
    try:
        result = await service.update(
            profile.id,
            profile.workspace_id,
            learning_id,
            **payload.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Learning not found")
    return result


@router.delete("/learnings/{learning_id}", status_code=204)
async def delete(
    learning_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[LearningService, Depends(get_service)],
):
    try:
        result = await service.delete(profile.id, profile.workspace_id, learning_id)
    except ValueError as error:
        raise not_found(error) from error
    if not result:
        raise HTTPException(404, "Learning not found")
