from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.database import get_db_session
from app.models.workspace_member import WorkspaceMember
from app.schemas.topic import TopicCreate, TopicResponse, TopicUpdate
from app.services.topic import TopicService

router = APIRouter(
    prefix="/market-intelligence/{market_id}/topics",
    tags=["Topics"],
)


async def get_topic_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TopicService:
    return TopicService(session)


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    market_id: UUID,
    payload: TopicCreate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[TopicService, Depends(get_topic_service)],
) -> TopicResponse:
    try:
        topic = await service.create(
            market_intelligence_id=market_id,
            workspace_id=workspace_member.workspace_id,
            name=payload.name,
            description=payload.description,
            relevance_score=payload.relevance_score,
        )
        return TopicResponse.model_validate(topic)
    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[TopicResponse])
async def list_topics(
    market_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[TopicService, Depends(get_topic_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[TopicResponse]:
    try:
        topics = await service.list(
            market_intelligence_id=market_id,
            workspace_id=workspace_member.workspace_id,
            skip=skip,
            limit=limit,
        )
        return [TopicResponse.model_validate(t) for t in topics]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    market_id: UUID,
    topic_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[TopicService, Depends(get_topic_service)],
) -> TopicResponse:
    try:
        topic = await service.get(
            market_intelligence_id=market_id,
            topic_id=topic_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found",
            )
        return TopicResponse.model_validate(topic)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    market_id: UUID,
    topic_id: UUID,
    payload: TopicUpdate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[TopicService, Depends(get_topic_service)],
) -> TopicResponse:
    try:
        topic = await service.update(
            market_intelligence_id=market_id,
            topic_id=topic_id,
            workspace_id=workspace_member.workspace_id,
            name=payload.name,
            description=payload.description,
            relevance_score=payload.relevance_score,
        )
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found",
            )
        return TopicResponse.model_validate(topic)
    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    market_id: UUID,
    topic_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[TopicService, Depends(get_topic_service)],
) -> None:
    try:
        success = await service.delete(
            market_intelligence_id=market_id,
            topic_id=topic_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market intelligence not found or workspace access denied",
        ) from e
