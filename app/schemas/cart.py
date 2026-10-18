from decimal import Decimal
from typing import List, Optional
from pydantic import Field
from app.schemas.base import CamelCaseModel

MAX_CART_QUANTITY_PER_ITEM = 99


class AddCartItemRequest(CamelCaseModel):
    product_id: int = Field(..., ge=1)
    quantity: int = Field(default=1, ge=1, le=MAX_CART_QUANTITY_PER_ITEM)


class UpdateCartItemRequest(CamelCaseModel):
    quantity: int = Field(..., ge=1, le=MAX_CART_QUANTITY_PER_ITEM)


class CartItemResponse(CamelCaseModel):
    cart_item_id: int
    product_id: int
    name: str
    sku: str
    unit: str
    image_url: Optional[str] = None
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    available_quantity: int
    is_available: bool
    can_checkout: bool


class CartResponse(CamelCaseModel):
    items: List[CartItemResponse] = Field(default_factory=list)
    item_count: int = 0
    subtotal: Decimal = Decimal("0.00")
    has_issues: bool = False

