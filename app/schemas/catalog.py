from decimal import Decimal
from typing import Optional
from pydantic import Field
from app.schemas.base import CamelCaseModel


class CategoryResponse(CamelCaseModel):
    category_id: int
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    product_count: int = 0


class ProductListItem(CamelCaseModel):
    product_id: int
    name: str
    sku: str
    price: Decimal
    unit: str
    image_url: Optional[str] = None
    category_id: int
    category_name: str
    in_stock: bool


class ProductDetailResponse(ProductListItem):
    description: Optional[str] = None
    stock_quantity: int

