import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import Field
from app.models.order import OrderStatus
from app.schemas.address import AddressResponse
from app.schemas.base import CamelCaseModel
from app.schemas.order import OrderItemResponse
from app.schemas.payment import PaymentResponse


class AdminOrderListItem(CamelCaseModel):
    order_id: int
    customer_id: int
    customer_name: str
    customer_email: str
    status: OrderStatus
    total_amount: Decimal
    item_count: int
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None


class ChangeOrderStatusRequest(CamelCaseModel):
    status: OrderStatus


class AdminCancelOrderRequest(CamelCaseModel):
    reason: str = Field(..., min_length=3, max_length=255)


class RecordRefundRequest(CamelCaseModel):
    amount: Optional[Decimal] = Field(None, ge=0)
    transaction_id: Optional[str] = Field(None, max_length=100)
    reason: str = Field(..., min_length=3, max_length=255)


class AdminOrderDetailResponse(CamelCaseModel):
    order_id: int
    customer_id: int
    customer_username: str
    customer_email: str
    customer_phone: Optional[str] = None
    status: OrderStatus
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total_amount: Decimal
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None
    delivery_address: Optional[AddressResponse] = None
    items: List[OrderItemResponse] = Field(default_factory=list)
    payments: List[PaymentResponse] = Field(default_factory=list)
    allowed_next_statuses: List[str] = Field(default_factory=list)
    can_cancel: bool
    refund_needed: bool

