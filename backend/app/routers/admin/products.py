import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.errors import AppError
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.admin_catalog import (
    AdminProductListItem,
    CreateProductRequest,
    UpdateProductRequest,
)
from app.schemas.common import PagedResult
from app.services.admin_catalog_service import AdminCatalogService

router = APIRouter(prefix="/api/admin/products", tags=["Admin Products"])

UPLOAD_DIR = Path("uploads/products")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("", response_model=PagedResult[AdminProductListItem])
def list_products(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None, alias="categoryId"),
    is_active: Optional[bool] = Query(None, alias="isActive"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = AdminCatalogService(db)
    return service.list_products(
        search=search,
        category_id=category_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AdminProductListItem)
def create_product(
    request: Request,
    body: CreateProductRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminCatalogService(db)
    return service.create_product(employee.id, body, get_client_ip(request))


@router.put("/{id}", response_model=AdminProductListItem)
def update_product(
    id: int,
    request: Request,
    body: UpdateProductRequest,
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = AdminCatalogService(db)
    return service.update_product(employee.id, id, body, get_client_ip(request))


@router.post("/{id}/image", response_model=AdminProductListItem)
async def upload_product_image(
    id: int,
    request: Request,
    file: UploadFile = File(...),
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise AppError.bad_request("Uploaded file must be an image.")

    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "webp"
    filename = f"prod_{id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = UPLOAD_DIR / filename

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    image_url = f"/uploads/products/{filename}"
    service = AdminCatalogService(db)
    return service.update_product(
        employee.id,
        id,
        UpdateProductRequest(image_url=image_url),
        get_client_ip(request),
    )

