import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.admin_order import (
    AdminCancelOrderRequest,
    AdminOrderDetailResponse,
    AdminOrderListItem,
    ChangeOrderStatusRequest,
    RecordRefundRequest,
)
from app.schemas.common import PagedResult
from app.services.admin_order_service import AdminOrderService

router = APIRouter(prefix="/api/admin/orders", tags=["Admin Orders"])


@router.get("", response_model=PagedResult[AdminOrderListItem])
def list_orders(
    status: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None, alias="paymentMethod"),
    date_from: Optional[datetime.date] = Query(None, alias="dateFrom"),
    date_to: Optional[datetime.date] = Query(None, alias="dateTo"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminOrderService(db)
    return service.list_orders(
        status=status,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=AdminOrderDetailResponse)
def get_order_detail(
    id: int,
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminOrderService(db)
    return service.get_order_detail(id)


@router.post("/{id}/status", response_model=AdminOrderDetailResponse)
def change_order_status(
    id: int,
    request: Request,
    body: ChangeOrderStatusRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminOrderService(db)
    return service.change_status(employee.id, id, body.status, get_client_ip(request))


@router.post("/{id}/cancel", response_model=AdminOrderDetailResponse)
def cancel_order(
    id: int,
    request: Request,
    body: AdminCancelOrderRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminOrderService(db)
    return service.cancel_order(employee.id, id, body.reason, get_client_ip(request))


@router.post("/{id}/mark-cash-paid", response_model=AdminOrderDetailResponse)
def mark_cash_paid(
    id: int,
    request: Request,
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminOrderService(db)
    return service.mark_cash_paid(employee.id, id, get_client_ip(request))


@router.post("/{id}/record-refund", response_model=AdminOrderDetailResponse)
def record_refund(
    id: int,
    request: Request,
    body: RecordRefundRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminOrderService(db)
    return service.record_refund(employee.id, id, body, get_client_ip(request))

