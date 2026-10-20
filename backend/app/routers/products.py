from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.catalog import ProductDetailResponse, ProductListItem
from app.schemas.common import PagedResult
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("", response_model=PagedResult[ProductListItem])
def search_products(
    search: Optional[str] = Query(None, max_length=100),
    category_id: Optional[int] = Query(None, alias="categoryId"),
    min_price: Optional[Decimal] = Query(None, alias="minPrice", ge=0, le=1000000),
    max_price: Optional[Decimal] = Query(None, alias="maxPrice", ge=0, le=1000000),
    in_stock_only: bool = Query(False, alias="inStockOnly"),
    sort: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    db: Session = Depends(get_db),
):
    service = CatalogService(db)
    return service.search_products(
        search=search,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=ProductDetailResponse)
def get_product_by_id(id: int, db: Session = Depends(get_db)):
    service = CatalogService(db)
    return service.get_product(id)

