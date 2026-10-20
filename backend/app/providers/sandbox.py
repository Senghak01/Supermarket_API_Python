import uuid
from app.models.order import Order
from app.models.payment import Payment, PaymentMethod
from app.providers.base import BasePaymentProvider, PaymentInitResult


class SandboxPaymentProvider(BasePaymentProvider):
    """Development-only payment provider simulating online payments for mobile testing."""

    def __init__(self, method: PaymentMethod) -> None:
        self._method = method

    @property
    def method(self) -> PaymentMethod:
        return self._method

    @property
    def requires_online_payment(self) -> bool:
        return True

    async def initiate(self, order: Order, payment: Payment) -> PaymentInitResult:
        short_id = uuid.uuid4().hex[:8]
        tx_id = f"SBX-{payment.id}-{short_id}"

        if self._method == PaymentMethod.Khqr:
            qr_data = f"SANDBOX-KHQR|order={order.id}|amount={payment.amount:.2f}|bill=P{payment.id}"
            return PaymentInitResult(transaction_id=tx_id, qr_data=qr_data)
        else:
            payment_url = f"https://sandbox.invalid/pay/{payment.id}"
            return PaymentInitResult(transaction_id=tx_id, payment_url=payment_url)

