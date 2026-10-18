from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.admin_catalog import CreateCategoryRequest, UpdateCategoryRequest
from app.schemas.catalog import CategoryResponse
from app.services.admin_catalog_service import AdminCatalogService

router = APIRouter(prefix="/api/admin/categories", tags=["Admin Categories"])


@router.get("", response_model=List[CategoryResponse])
def list_categories(
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminCatalogService(db)
    return service.list_categories()


@router.post("", response_model=CategoryResponse)
def create_category(
    request: Request,
    body: CreateCategoryRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminCatalogService(db)
    return service.create_category(employee.id, body, get_client_ip(request))


@router.put("/{id}", response_model=CategoryResponse)
def update_category(
    id: int,
    request: Request,
    body: UpdateCategoryRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminCatalogService(db)
    return service.update_category(employee.id, id, body, get_client_ip(request))

