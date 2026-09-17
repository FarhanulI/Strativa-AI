from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import require_workspace_access
from app.core.database import get_db_session
from app.models.workspace_member import WorkspaceMember
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product import ProductService

router = APIRouter(prefix="/business-context", tags=["Products"])


async def get_product_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductService:
    return ProductService(session)


@router.post(
    "/{business_context_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    business_context_id: UUID,
    payload: ProductCreate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductResponse:
    """
    Create a new product for a business context.
    """
    try:
        product = await service.create(
            business_context_id=business_context_id,
            workspace_id=workspace_member.workspace_id,
            name=payload.name,
            description=payload.description,
            category=payload.category,
            price=payload.price,
            currency=payload.currency,
            features=payload.features,
            benefits=payload.benefits,
            target_audience=payload.target_audience,
        )
        return ProductResponse.model_validate(product)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{business_context_id}/products", response_model=list[ProductResponse])
async def list_products(
    business_context_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> list[ProductResponse]:
    """
    List all products for a business context within a workspace.
    """
    products = await service.list(business_context_id, workspace_member.workspace_id)
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/{business_context_id}/products/{product_id}", response_model=ProductResponse)
async def get_product(
    business_context_id: UUID,
    product_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductResponse:
    """
    Get a product by ID within a workspace.
    """
    product = await service.get(product_id, business_context_id, workspace_member.workspace_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return ProductResponse.model_validate(product)


@router.patch(
    "/{business_context_id}/products/{product_id}",
    response_model=ProductResponse,
)
async def update_product(
    business_context_id: UUID,
    product_id: UUID,
    payload: ProductUpdate,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductResponse:
    """
    Update a product within a workspace.
    """
    product = await service.update(
        product_id=product_id,
        business_context_id=business_context_id,
        workspace_id=workspace_member.workspace_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        price=payload.price,
        currency=payload.currency,
        features=payload.features,
        benefits=payload.benefits,
        target_audience=payload.target_audience,
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return ProductResponse.model_validate(product)


@router.delete(
    "/{business_context_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(
    business_context_id: UUID,
    product_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> None:
    """
    Delete a product within a workspace.
    """
    deleted = await service.delete(product_id, business_context_id, workspace_member.workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
