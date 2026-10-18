import datetime
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.errors import AppError
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.providers.bakong_khqr import BakongKhqrProvider
from app.providers.base import BasePaymentProvider, BasePaymentVerifier
from app.providers.cash_on_delivery import CashOnDeliveryProvider
from app.providers.sandbox import SandboxPaymentProvider
from app.schemas.payment import InitiatePaymentRequest, PaymentResponse

logger = logging.getLogger("supermarket.payment")


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.providers: Dict[PaymentMethod, BasePaymentProvider] = {}
        self._register_providers()

    def _register_providers(self) -> None:
        # Cash on delivery is always available
        cod = CashOnDeliveryProvider()
        self.providers[cod.method] = cod

        # Bakong KHQR if enabled
        if settings.BAKONG_ENABLED:
            bakong = BakongKhqrProvider()
            self.providers[bakong.method] = bakong

        # Sandbox providers for development testing
        if settings.ENABLE_SANDBOX_PAYMENTS:
            if PaymentMethod.Khqr not in self.providers:
                self.providers[PaymentMethod.Khqr] = SandboxPaymentProvider(PaymentMethod.Khqr)
            self.providers[PaymentMethod.Card] = SandboxPaymentProvider(PaymentMethod.Card)

    async def initiate_payment(
        self,
        customer_id: int,
        order_id: int,
        request: InitiatePaymentRequest,
    ) -> PaymentResponse:
        # Parse method
        method_str = request.method.strip()
        try:
            method = PaymentMethod(method_str)
        except ValueError:
            raise AppError.bad_request("Unknown payment method. Use CashOnDelivery, Khqr or Card.")

        order = self.db.scalar(
            select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
        )
        if not order:
            raise AppError.not_found("Order not found.")

        if order.status != OrderStatus.Pending.value:
            raise AppError.conflict("This order can no longer be paid.")

        provider = self.providers.get(method)
        if not provider:
            raise AppError.bad_request("This payment method is not available yet.")

        # A new payment attempt cancels any earlier unpaid attempt
        self.db.execute(
            update(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.Pending.value,
            )
            .values(status=PaymentStatus.Cancelled.value)
        )

        payment = Payment(
            order_id=order_id,
            method=method.value,
            status=PaymentStatus.Pending.value,
            amount=order.total_amount,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(payment)
        self.db.flush()  # Assigns payment.id

        try:
            init_result = await provider.initiate(order, payment)
        except Exception as ex:
            logger.exception(f"Payment provider {method} failed to start payment {payment.id}: {ex}")
            payment.status = PaymentStatus.Failed.value
            self.db.commit()
            raise AppError(status_code=502, message="Could not start the payment. Please try again.")

        if init_result.transaction_id:
            payment.transaction_id = init_result.transaction_id

        expires_at: Optional[datetime.datetime] = None
        if provider.requires_online_payment:
            expires_at = order.created_at + datetime.timedelta(minutes=settings.UNPAID_ORDER_EXPIRY_MINUTES)
        else:
            # Cash on delivery: nothing to wait for online, so order becomes Confirmed
            # Payment stays Pending until collected by courier
            self.db.execute(
                update(Order)
                .where(Order.id == order_id, Order.status == OrderStatus.Pending.value)
                .values(
                    status=OrderStatus.Confirmed.value,
                    updated_at=datetime.datetime.now(datetime.timezone.utc),
                )
            )

        self.db.commit()
        self.db.refresh(payment)

        return self._to_response(
            payment,
            payment_url=init_result.payment_url,
            qr_data=init_result.qr_data,
            expires_at=expires_at,
        )

    def get_for_order(self, customer_id: int, order_id: int) -> List[PaymentResponse]:
        order = self.db.scalar(
            select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
        )
        if not order:
            raise AppError.not_found("Order not found.")

        payments = self.db.scalars(
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.id.desc())
        ).all()

        return [self._to_response(p) for p in payments]

    async def refresh_payment(self, customer_id: int, payment_id: int) -> PaymentResponse:
        payment = self.db.scalar(
            select(Payment)
            .join(Order, Payment.order_id == Order.id)
            .where(Payment.id == payment_id, Order.customer_id == customer_id)
        )
        if not payment:
            raise AppError.not_found("Payment not found.")

        if payment.status == PaymentStatus.Pending.value:
            await self._verify_and_mark_paid(payment)

        self.db.refresh(payment)
        return self._to_response(payment)

    async def sandbox_confirm(self, customer_id: int, payment_id: int) -> PaymentResponse:
        if not settings.ENABLE_SANDBOX_PAYMENTS:
            raise AppError.forbidden("Sandbox payments are disabled in this environment.")

        payment = self.db.scalar(
            select(Payment)
            .join(Order, Payment.order_id == Order.id)
            .where(Payment.id == payment_id, Order.customer_id == customer_id)
        )
        if not payment:
            raise AppError.not_found("Payment not found.")

        if payment.method == PaymentMethod.CashOnDelivery.value:
            raise AppError.bad_request("Cash on delivery is paid when the order is delivered.")

        return self.mark_paid(payment.id, f"SBX-PAID-{payment.id}")

    def mark_paid(self, payment_id: int, transaction_id: Optional[str]) -> PaymentResponse:
        payment = self.db.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment:
            raise AppError.not_found("Payment not found.")

        now = datetime.datetime.now(datetime.timezone.utc)

        # Lock order: Orders first, then Payments (same as cancel to prevent deadlocks)
        confirmed_rows = self.db.execute(
            update(Order)
            .where(Order.id == payment.order_id, Order.status == OrderStatus.Pending.value)
            .values(status=OrderStatus.Confirmed.value, updated_at=now)
        ).rowcount

        paid_rows = self.db.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status != PaymentStatus.Paid.value)
            .values(
                status=PaymentStatus.Paid.value,
                paid_at=now,
                transaction_id=payment.transaction_id or transaction_id,
            )
        ).rowcount

        self.db.commit()

        # Late payment on cancelled order check
        if paid_rows == 1 and confirmed_rows == 0:
            order_status = self.db.scalar(
                select(Order.status).where(Order.id == payment.order_id)
            )
            if order_status == OrderStatus.Cancelled.value:
                logger.warning(
                    f"REFUND NEEDED: Payment {payment_id} was received for cancelled order {payment.order_id}. "
                    "Customer must be refunded."
                )

        self.db.refresh(payment)
        return self._to_response(payment)

    async def verify_pending_payments(self, created_after: datetime.datetime) -> int:
        """Background job helper: queries pending online payments from past 35 minutes (max 50)."""
        stmt = (
            select(Payment)
            .where(
                Payment.status == PaymentStatus.Pending.value,
                Payment.method != PaymentMethod.CashOnDelivery.value,
                Payment.created_at > created_after,
            )
            .order_by(Payment.id.asc())
            .limit(50)
        )
        pending = self.db.scalars(stmt).all()

        paid_count = 0
        for p in pending:
            if await self._verify_and_mark_paid(p):
                paid_count += 1

        return paid_count

    async def _verify_and_mark_paid(self, payment: Payment) -> bool:
        try:
            method = PaymentMethod(payment.method)
        except ValueError:
            return False

        provider = self.providers.get(method)
        if not isinstance(provider, BasePaymentVerifier):
            return False

        try:
            verification = await provider.verify(payment)
        except Exception as ex:
            logger.error(f"Could not verify payment {payment.id} with provider: {ex}")
            return False

        if not verification.paid:
            return False

        self.mark_paid(payment.id, verification.provider_reference)
        return True

    def _to_response(
        self,
        payment: Payment,
        payment_url: Optional[str] = None,
        qr_data: Optional[str] = None,
        expires_at: Optional[datetime.datetime] = None,
    ) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment.id,
            order_id=payment.order_id,
            method=PaymentMethod(payment.method),
            status=PaymentStatus(payment.status),
            amount=payment.amount,
            transaction_id=payment.transaction_id,
            payment_url=payment_url,
            qr_data=qr_data,
            expires_at=expires_at,
            created_at=payment.created_at,
            paid_at=payment.paid_at,
        )

