import datetime
from decimal import Decimal
from typing import Optional
from pydantic import Field
from app.models.payment import PaymentMethod, PaymentStatus
from app.schemas.base import CamelCaseModel


class InitiatePaymentRequest(CamelCaseModel):
    # CashOnDelivery | Khqr | Card
    method: str = Field(..., min_length=1, max_length=30)


class PaymentSummaryResponse(CamelCaseModel):
    payment_id: int
    method: PaymentMethod
    status: PaymentStatus
    amount: Decimal
    paid_at: Optional[datetime.datetime] = None


class PaymentResponse(CamelCaseModel):
    payment_id: int
    order_id: int
    method: PaymentMethod
    status: PaymentStatus
    amount: Decimal
    transaction_id: Optional[str] = None
    payment_url: Optional[str] = None
    qr_data: Optional[str] = None
    expires_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    paid_at: Optional[datetime.datetime] = None

