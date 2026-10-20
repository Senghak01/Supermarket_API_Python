from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.deps import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.common import PagedResult
from app.schemas.order import (
    OrderDetailResponse,
    OrderSummaryResponse,
    PlaceOrderRequest,
)
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post("", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
def place_order(
    body: PlaceOrderRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = OrderService(db)
    return service.place_order(customer.id, body)


@router.get("", response_model=PagedResult[OrderSummaryResponse])
def get_order_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = OrderService(db)
    return service.get_all(customer.id, page=page, page_size=page_size)


@router.get("/{id}", response_model=OrderDetailResponse)
def get_order_detail(
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = OrderService(db)
    return service.get_by_id(customer.id, id)


@router.post("/{id}/cancel", response_model=OrderDetailResponse)
def cancel_order(
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = OrderService(db)
    return service.cancel_order(customer.id, id)

