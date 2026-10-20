from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from app.models.order import Order
from app.models.payment import Payment, PaymentMethod


@dataclass
class PaymentInitResult:
    transaction_id: Optional[str] = None
    payment_url: Optional[str] = None
    qr_data: Optional[str] = None


@dataclass
class PaymentVerification:
    paid: bool = False
    provider_reference: Optional[str] = None


class BasePaymentProvider(ABC):
    @property
    @abstractmethod
    def method(self) -> PaymentMethod:
        pass

    @property
    @abstractmethod
    def requires_online_payment(self) -> bool:
        pass

    @abstractmethod
    async def initiate(self, order: Order, payment: Payment) -> PaymentInitResult:
        pass


class BasePaymentVerifier(ABC):
    @abstractmethod
    async def verify(self, payment: Payment) -> PaymentVerification:
        pass

