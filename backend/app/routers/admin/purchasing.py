from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.common import PagedResult
from app.schemas.purchasing import (
    PurchaseOrderCreateRequest,
    PurchaseOrderResponse,
    SupplierCreateRequest,
    SupplierResponse,
    SupplierUpdateRequest,
)
from app.services.purchasing_service import PurchasingService

router = APIRouter(prefix="/api/admin/purchasing", tags=["Admin Purchasing"])


# --- Suppliers ---

@router.get("/suppliers", response_model=List[SupplierResponse])
def list_suppliers(
    active_only: bool = Query(False, alias="activeOnly"),
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.list_suppliers(active_only=active_only)


@router.post("/suppliers", response_model=SupplierResponse)
def create_supplier(
    request: Request,
    body: SupplierCreateRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.create_supplier(employee.id, body, get_client_ip(request))


@router.put("/suppliers/{id}", response_model=SupplierResponse)
def update_supplier(
    id: int,
    request: Request,
    body: SupplierUpdateRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.update_supplier(employee.id, id, body, get_client_ip(request))


# --- Purchase Orders ---

@router.get("/orders", response_model=PagedResult[PurchaseOrderResponse])
def list_purchases(
    supplier_id: Optional[int] = Query(None, alias="supplierId"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.list_purchases(
        supplier_id=supplier_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{id}", response_model=PurchaseOrderResponse)
def get_purchase(
    id: int,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.get_purchase(id)


@router.post("/orders", response_model=PurchaseOrderResponse)
def create_purchase(
    request: Request,
    body: PurchaseOrderCreateRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.create_purchase(employee.id, body, get_client_ip(request))


@router.post("/orders/{id}/receive", response_model=PurchaseOrderResponse)
def receive_stock(
    id: int,
    request: Request,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = PurchasingService(db)
    return service.receive_stock(employee.id, id, get_client_ip(request))

