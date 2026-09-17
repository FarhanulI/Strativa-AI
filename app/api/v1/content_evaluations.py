"""
Content evaluation API endpoints.

Provides evaluation of content drafts against their strategic briefs.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_profile_access
from app.core.database import get_db_session
from app.models.content_profile import ContentProfile
from app.repositories.content_brief import ContentBriefRepository
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_draft_variation import ContentDraftVariationRepository
from app.repositories.content_evaluation import ContentEvaluationRepository
from app.repositories.content_profile import ContentProfileRepository
from app.schemas.content_evaluation import (
    ContentEvaluationCreateRequest,
    ContentEvaluationListResponse,
    ContentEvaluationResponse,
)
from app.services.evaluation.evaluator import ContentEvaluationService

router = APIRouter(tags=["Content Evaluations"])


async def get_evaluation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentEvaluationService:
    """Dependency injection for evaluation service."""
    profile_repo = ContentProfileRepository(session)
    draft_repo = ContentDraftRepository(session)
    brief_repo = ContentBriefRepository(session)
    variation_repo = ContentDraftVariationRepository(session)
    evaluation_repo = ContentEvaluationRepository(session)
    # AIRouter is optional - service creates default if not provided

    return ContentEvaluationService(
        session,
        profile_repo,
        draft_repo,
        brief_repo,
        variation_repo,
        evaluation_repo,
    )


def not_found(error: ValueError) -> HTTPException:
    """Convert ValueError to 404 HTTPException."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/profiles/{profile_id}/drafts/{draft_id}/evaluations",
    response_model=ContentEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_draft(
    draft_id: UUID,
    payload: ContentEvaluationCreateRequest,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    service: Annotated[ContentEvaluationService, Depends(get_evaluation_service)],
) -> ContentEvaluationResponse:
    """
    Evaluate a content draft against its strategic brief.

    Supports both deterministic and AI-powered evaluation with automatic fallback.

    **Request Body:**
    - use_ai: bool - Whether to attempt AI enrichment (defaults to true)
    - variation_id: UUID (optional) - Specific variation to evaluate

    **Returns:**
    - 201: ContentEvaluationResponse with scores, classification, and findings
    - 404: If profile, draft, brief, or variation not found or ownership mismatch
    """
    try:
        evaluation = await service.evaluate_draft(
            profile.id,
            profile.workspace_id,
            draft_id,
            variation_id=payload.variation_id,
            use_ai=payload.use_ai,
        )
    except ValueError as error:
        raise not_found(error) from error
    return evaluation


@router.get(
    "/profiles/{profile_id}/drafts/{draft_id}/evaluations",
    response_model=ContentEvaluationListResponse,
)
async def list_draft_evaluations(
    draft_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort: str = Query("desc", description="Sort direction (asc/desc)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> ContentEvaluationListResponse:
    """
    List evaluations for a specific draft.

    Returns evaluations in reverse chronological order (newest first).

    **Query Parameters:**
    - sort_by: str - Field to sort by (default: created_at)
    - sort: str - Sort direction (asc/desc, default: desc)
    - skip: int - Number of results to skip (default: 0)
    - limit: int - Maximum results to return (default: 100, max: 100)

    **Returns:**
    - 200: ContentEvaluationListResponse with paginated results
    - 404: If draft not found
    """
    draft_repo = ContentDraftRepository(session)

    try:
        draft = await draft_repo.get_by_id(profile.id, draft_id)
        if not draft:
            raise ValueError("Content draft not found")
    except ValueError as error:
        raise not_found(error) from error

    evaluation_repo = ContentEvaluationRepository(session)
    evaluations, total = await evaluation_repo.list_evaluations_for_draft(
        profile.id, draft_id, sort_by=sort_by, sort_order=sort, skip=skip, limit=limit
    )

    return ContentEvaluationListResponse(
        evaluations=[ContentEvaluationResponse.model_validate(e) for e in evaluations],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/profiles/{profile_id}/drafts/{draft_id}/evaluations/{evaluation_id}",
    response_model=ContentEvaluationResponse,
)
async def get_draft_evaluation(
    draft_id: UUID,
    evaluation_id: UUID,
    profile: Annotated[ContentProfile, Depends(require_profile_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentEvaluationResponse:
    """
    Get a specific evaluation by ID.

    **Returns:**
    - 200: ContentEvaluationResponse with full evaluation details
    - 404: If draft or evaluation not found or ownership mismatch
    """
    draft_repo = ContentDraftRepository(session)
    evaluation_repo = ContentEvaluationRepository(session)

    try:
        draft = await draft_repo.get_by_id(profile.id, draft_id)
        if not draft:
            raise ValueError("Content draft not found")

        evaluation = await evaluation_repo.get_evaluation(evaluation_id, profile.id)
        if not evaluation:
            raise ValueError("Content evaluation not found")

        # Verify evaluation belongs to the requested draft
        if evaluation.draft_id != draft_id:
            raise ValueError("Content evaluation not found")
    except ValueError as error:
        raise not_found(error) from error

    return ContentEvaluationResponse.model_validate(evaluation)
