from app.models.order import Order
from app.models.payment import Payment, PaymentMethod
from app.providers.base import BasePaymentProvider, PaymentInitResult


class CashOnDeliveryProvider(BasePaymentProvider):
    @property
    def method(self) -> PaymentMethod:
        return PaymentMethod.CashOnDelivery

    @property
    def requires_online_payment(self) -> bool:
        return False

    async def initiate(self, order: Order, payment: Payment) -> PaymentInitResult:
        return PaymentInitResult()

