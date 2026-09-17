from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.database import get_db_session
from app.models.workspace_member import WorkspaceMember
from app.schemas.audience_question import (
    AudienceQuestionCreate,
    AudienceQuestionResponse,
    AudienceQuestionUpdate,
)
from app.services.audience_question import AudienceQuestionService

router = APIRouter(
    prefix="/audience-intelligence/{audience_id}/questions",
    tags=["Audience Questions"],
)


async def get_audience_question_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AudienceQuestionService:
    return AudienceQuestionService(session)


@router.post("", response_model=AudienceQuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_audience_question(
    audience_id: UUID,
    payload: AudienceQuestionCreate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceQuestionService, Depends(get_audience_question_service)],
) -> AudienceQuestionResponse:
    try:
        question = await service.create(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_member.workspace_id,
            question=payload.question,
            context=payload.context,
            evidence=payload.evidence,
            frequency=payload.frequency,
            importance=payload.importance,
        )
        return AudienceQuestionResponse.model_validate(question)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("", response_model=list[AudienceQuestionResponse])
async def list_audience_questions(
    audience_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceQuestionService, Depends(get_audience_question_service)],
    skip: int = 0,
    limit: int = 100,
) -> list[AudienceQuestionResponse]:
    try:
        questions = await service.list(
            audience_intelligence_id=audience_id,
            workspace_id=workspace_member.workspace_id,
            skip=skip,
            limit=limit,
        )
        return [AudienceQuestionResponse.model_validate(q) for q in questions]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.get("/{question_id}", response_model=AudienceQuestionResponse)
async def get_audience_question(
    audience_id: UUID,
    question_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceQuestionService, Depends(get_audience_question_service)],
) -> AudienceQuestionResponse:
    try:
        question = await service.get(
            audience_intelligence_id=audience_id,
            question_id=question_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found",
            )
        return AudienceQuestionResponse.model_validate(question)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.patch("/{question_id}", response_model=AudienceQuestionResponse)
async def update_audience_question(
    audience_id: UUID,
    question_id: UUID,
    payload: AudienceQuestionUpdate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceQuestionService, Depends(get_audience_question_service)],
) -> AudienceQuestionResponse:
    try:
        question = await service.update(
            audience_intelligence_id=audience_id,
            question_id=question_id,
            workspace_id=workspace_member.workspace_id,
            question=payload.question,
            context=payload.context,
            evidence=payload.evidence,
            frequency=payload.frequency,
            importance=payload.importance,
        )
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found",
            )
        return AudienceQuestionResponse.model_validate(question)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audience_question(
    audience_id: UUID,
    question_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[AudienceQuestionService, Depends(get_audience_question_service)],
) -> None:
    try:
        success = await service.delete(
            audience_intelligence_id=audience_id,
            question_id=question_id,
            workspace_id=workspace_member.workspace_id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audience intelligence not found or workspace access denied",
        ) from e
