from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.catalog import CategoryResponse
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    service = CatalogService(db)
    return service.get_categories()


@router.get("/{id}", response_model=CategoryResponse)
def get_category_by_id(id: int, db: Session = Depends(get_db)):
    service = CatalogService(db)
    return service.get_category(id)

