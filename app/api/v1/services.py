from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.service import ServiceService

router = APIRouter(prefix="/business-context", tags=["Services"])


async def get_service_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ServiceService:
    return ServiceService(session)


@router.post(
    "/{business_context_id}/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    business_context_id: UUID,
    payload: ServiceCreate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    """
    Create a new service for a business context.
    """
    try:
        result = await service.create(
            business_context_id=business_context_id,
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            category=payload.category,
            price=payload.price,
            currency=payload.currency,
            features=payload.features,
            benefits=payload.benefits,
            target_audience=payload.target_audience,
        )
        return ServiceResponse.model_validate(result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{business_context_id}/services", response_model=list[ServiceResponse])
async def list_services(
    business_context_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> list[ServiceResponse]:
    """
    List all services for a business context within a workspace.
    """
    services = await service.list(business_context_id, workspace_id)
    return [ServiceResponse.model_validate(s) for s in services]


@router.get("/{business_context_id}/services/{service_id}", response_model=ServiceResponse)
async def get_service(
    business_context_id: UUID,
    service_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    """
    Get a service by ID within a workspace.
    """
    result = await service.get(service_id, business_context_id, workspace_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    return ServiceResponse.model_validate(result)


@router.patch(
    "/{business_context_id}/services/{service_id}",
    response_model=ServiceResponse,
)
async def update_service(
    business_context_id: UUID,
    service_id: UUID,
    payload: ServiceUpdate,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    """
    Update a service within a workspace.
    """
    result = await service.update(
        service_id=service_id,
        business_context_id=business_context_id,
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        price=payload.price,
        currency=payload.currency,
        features=payload.features,
        benefits=payload.benefits,
        target_audience=payload.target_audience,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    return ServiceResponse.model_validate(result)


@router.delete(
    "/{business_context_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_service(
    business_context_id: UUID,
    service_id: UUID,
    workspace_id: Annotated[UUID, Query(..., description="The workspace ID")],
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> None:
    """
    Delete a service within a workspace.
    """
    deleted = await service.delete(service_id, business_context_id, workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
