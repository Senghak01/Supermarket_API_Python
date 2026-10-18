from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.admin_inventory import (
    InventoryListItem,
    StockAdjustmentRequest,
    StockMovementListItem,
)
from app.schemas.common import PagedResult
from app.services.admin_inventory_service import AdminInventoryService

router = APIRouter(prefix="/api/admin/inventory", tags=["Admin Inventory"])


@router.get("", response_model=PagedResult[InventoryListItem])
def list_inventory(
    search: Optional[str] = Query(None),
    low_stock_only: bool = Query(False, alias="lowStockOnly"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminInventoryService(db)
    return service.list_inventory(
        search=search,
        low_stock_only=low_stock_only,
        page=page,
        page_size=page_size,
    )


@router.post("/adjust", response_model=InventoryListItem)
def adjust_stock(
    request: Request,
    body: StockAdjustmentRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminInventoryService(db)
    return service.adjust_stock(employee.id, body, get_client_ip(request))


@router.get("/movements", response_model=PagedResult[StockMovementListItem])
def get_stock_movements(
    product_id: Optional[int] = Query(None, alias="productId"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminInventoryService(db)
    return service.get_movement_history(
        product_id=product_id,
        page=page,
        page_size=page_size,
    )

