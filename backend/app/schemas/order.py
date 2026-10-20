import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import Field
from app.models.order import OrderStatus
from app.schemas.address import AddressResponse
from app.schemas.base import CamelCaseModel
from app.schemas.payment import PaymentSummaryResponse


class PlaceOrderRequest(CamelCaseModel):
    address_id: int = Field(..., ge=1)


class OrderSummaryResponse(CamelCaseModel):
    order_id: int
    status: OrderStatus
    total_amount: Decimal
    item_count: int
    created_at: datetime.datetime


class OrderItemResponse(CamelCaseModel):
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal


class OrderDetailResponse(CamelCaseModel):
    order_id: int
    status: OrderStatus
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total_amount: Decimal
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None
    can_cancel: bool
    payment: Optional[PaymentSummaryResponse] = None
    delivery_address: Optional[AddressResponse] = None
    items: List[OrderItemResponse] = Field(default_factory=list)

