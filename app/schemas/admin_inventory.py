import datetime
from decimal import Decimal
from typing import Optional
from pydantic import Field
from app.schemas.base import CamelCaseModel


class InventoryListItem(CamelCaseModel):
    product_id: int
    name: str
    sku: str
    category_name: str
    quantity: int
    unit: str
    price: Decimal
    is_active: bool
    is_low_stock: bool
    updated_at: datetime.datetime


class StockAdjustmentRequest(CamelCaseModel):
    product_id: int = Field(..., ge=1)
    delta: int = Field(..., description="Quantity change (can be positive or negative, non-zero)")
    reason: str = Field(..., min_length=3, max_length=255, description="Audit reason for stock change")


class StockMovementListItem(CamelCaseModel):
    id: int
    product_id: int
    product_name: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    movement_type: str
    quantity: int
    reference_id: Optional[int] = None
    created_at: datetime.datetime

