import datetime
from decimal import Decimal
from typing import List, Optional
from app.schemas.address import AddressResponse
from app.schemas.base import CamelCaseModel
from app.schemas.order import OrderSummaryResponse


class AdminCustomerListItem(CamelCaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    orders_count: int = 0
    total_spent: Decimal = Decimal("0.00")
    created_at: datetime.datetime


class AdminCustomerDetailResponse(CamelCaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    photo_url: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None
    addresses: List[AddressResponse] = []
    recent_orders: List[OrderSummaryResponse] = []

