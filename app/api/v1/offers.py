from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.offer import OfferCreate, OfferResponse, OfferUpdate
from app.services.offer import OfferService

router = APIRouter(prefix="/business-context", tags=["Offers"])


async def get_offer_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OfferService:
    return OfferService(session)


@router.post(
    "/{business_context_id}/offers",
    response_model=OfferResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_offer(
    business_context_id: UUID,
    payload: OfferCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[OfferService, Depends(get_offer_service)],
) -> OfferResponse:
    """
    Create a new offer for a business context.
    """
    try:
        offer = await service.create(
            business_context_id=business_context_id,
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            offer_type=payload.offer_type,
            value=payload.value,
            currency=payload.currency,
            terms=payload.terms,
            target_audience=payload.target_audience,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            active=payload.active,
        )
        return OfferResponse.model_validate(offer)
    except ValueError as e:
        if "must not be after" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{business_context_id}/offers", response_model=list[OfferResponse])
async def list_offers(
    business_context_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[OfferService, Depends(get_offer_service)],
) -> list[OfferResponse]:
    """
    List all offers for a business context within a workspace.
    """
    offers = await service.list(business_context_id, workspace_id)
    return [OfferResponse.model_validate(o) for o in offers]


@router.get("/{business_context_id}/offers/{offer_id}", response_model=OfferResponse)
async def get_offer(
    business_context_id: UUID,
    offer_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[OfferService, Depends(get_offer_service)],
) -> OfferResponse:
    """
    Get an offer by ID within a workspace.
    """
    offer = await service.get(offer_id, business_context_id, workspace_id)
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )
    return OfferResponse.model_validate(offer)


@router.patch(
    "/{business_context_id}/offers/{offer_id}",
    response_model=OfferResponse,
)
async def update_offer(
    business_context_id: UUID,
    offer_id: UUID,
    payload: OfferUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[OfferService, Depends(get_offer_service)],
) -> OfferResponse:
    """
    Update an offer within a workspace.
    """
    try:
        offer = await service.update(
            offer_id=offer_id,
            business_context_id=business_context_id,
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            offer_type=payload.offer_type,
            value=payload.value,
            currency=payload.currency,
            terms=payload.terms,
            target_audience=payload.target_audience,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            active=payload.active,
        )
        if not offer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )
        return OfferResponse.model_validate(offer)
    except ValueError as e:
        if "must not be after" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        raise


@router.delete(
    "/{business_context_id}/offers/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_offer(
    business_context_id: UUID,
    offer_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[OfferService, Depends(get_offer_service)],
) -> None:
    """
    Delete an offer within a workspace.
    """
    deleted = await service.delete(offer_id, business_context_id, workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )
