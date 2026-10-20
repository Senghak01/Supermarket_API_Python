from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.admin_customer import (
    AdminCustomerDetailResponse,
    AdminCustomerListItem,
)
from app.schemas.base import CamelCaseModel
from app.schemas.common import PagedResult
from app.services.admin_customer_service import AdminCustomerService

router = APIRouter(prefix="/api/admin/customers", tags=["Admin Customers"])


class ToggleCustomerStatusRequest(CamelCaseModel):
    is_active: bool


@router.get("", response_model=PagedResult[AdminCustomerListItem])
def list_customers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None, alias="isActive"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminCustomerService(db)
    return service.list_customers(
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=AdminCustomerDetailResponse)
def get_customer_detail(
    id: int,
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminCustomerService(db)
    return service.get_customer_detail(id)


@router.put("/{id}/status", response_model=AdminCustomerDetailResponse)
def toggle_customer_status(
    id: int,
    request: Request,
    body: ToggleCustomerStatusRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminCustomerService(db)
    return service.toggle_customer_status(employee.id, id, body.is_active, get_client_ip(request))

