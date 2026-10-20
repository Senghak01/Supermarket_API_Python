import datetime
from decimal import Decimal
from typing import Optional
from pydantic import Field
from app.schemas.base import CamelCaseModel


class CreateCategoryRequest(CamelCaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True


class UpdateCategoryRequest(CamelCaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class CreateProductRequest(CamelCaseModel):
    category_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=2, max_length=200)
    sku: str = Field(..., min_length=2, max_length=50)
    price: Decimal = Field(..., ge=0)
    unit: str = Field(default="item", max_length=20)
    description: Optional[str] = None
    image_url: Optional[str] = None
    initial_stock: int = Field(default=0, ge=0)
    is_active: bool = True


class UpdateProductRequest(CamelCaseModel):
    category_id: Optional[int] = Field(None, ge=1)
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    sku: Optional[str] = Field(None, min_length=2, max_length=50)
    price: Optional[Decimal] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class AdminProductListItem(CamelCaseModel):
    product_id: int
    name: str
    sku: str
    price: Decimal
    unit: str
    image_url: Optional[str] = None
    category_id: int
    category_name: str
    stock_quantity: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

