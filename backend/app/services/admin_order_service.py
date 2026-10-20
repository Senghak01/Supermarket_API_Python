import datetime
import json
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.models.catalog import Inventory
from app.models.customer import Customer, CustomerAddress
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.stock_movement import StockMovement, StockMovementType
from app.schemas.address import AddressResponse
from app.schemas.admin_order import (
    AdminOrderDetailResponse,
    AdminOrderListItem,
    RecordRefundRequest,
)
from app.schemas.common import PagedResult
from app.schemas.order import OrderItemResponse
from app.schemas.payment import PaymentResponse

# Allowed status transitions for orders
ALLOWED_TRANSITIONS = {
    OrderStatus.Pending.value: [OrderStatus.Confirmed.value, OrderStatus.Cancelled.value],
    OrderStatus.Confirmed.value: [OrderStatus.Preparing.value, OrderStatus.Cancelled.value],
    OrderStatus.Preparing.value: [OrderStatus.ReadyForDelivery.value, OrderStatus.Cancelled.value],
    OrderStatus.ReadyForDelivery.value: [OrderStatus.OutForDelivery.value],
    OrderStatus.OutForDelivery.value: [OrderStatus.Delivered.value],
    OrderStatus.Delivered.value: [],
    OrderStatus.Cancelled.value: [],
}


class AdminOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_orders(
        self,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[AdminOrderListItem]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = (
            select(Order)
            .join(Customer, Order.customer_id == Customer.id)
            .options(
                joinedload(Order.customer),
                joinedload(Order.items),
                joinedload(Order.payments),
            )
        )

        if status:
            query = query.where(Order.status == status)

        if date_from:
            dt_from = datetime.datetime.combine(date_from, datetime.time.min).replace(tzinfo=datetime.timezone.utc)
            query = query.where(Order.created_at >= dt_from)

        if date_to:
            dt_to = datetime.datetime.combine(date_to, datetime.time.max).replace(tzinfo=datetime.timezone.utc)
            query = query.where(Order.created_at <= dt_to)

        if search and search.strip():
            term = f"%{search.strip()}%"
            # If search is a number, search order ID as well
            if search.strip().isdigit():
                query = query.where(
                    (Order.id == int(search.strip())) |
                    (Customer.username.ilike(term)) |
                    (Customer.email.ilike(term))
                )
            else:
                query = query.where(
                    (Customer.username.ilike(term)) |
                    (Customer.email.ilike(term))
                )

        count_query = select(func.count()).select_from(query.with_only_columns(Order.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        paged_query = query.order_by(Order.created_at.desc(), Order.id.desc()).offset((page - 1) * page_size).limit(page_size)
        orders = self.db.scalars(paged_query).unique().all()

        items = []
        for o in orders:
            latest_payment = next((p for p in o.payments if p.status != PaymentStatus.Cancelled.value), None)
            if not latest_payment and o.payments:
                latest_payment = o.payments[0]

            if payment_method and latest_payment and latest_payment.method != payment_method:
                continue

            customer_name = (
                f"{o.customer.first_name or ''} {o.customer.last_name or ''}".strip()
                or o.customer.username
            )

            items.append(
                AdminOrderListItem(
                    order_id=o.id,
                    customer_id=o.customer_id,
                    customer_name=customer_name,
                    customer_email=o.customer.email,
                    status=OrderStatus(o.status),
                    total_amount=o.total_amount,
                    item_count=sum(i.quantity for i in o.items),
                    payment_method=latest_payment.method if latest_payment else None,
                    payment_status=latest_payment.status if latest_payment else None,
                    created_at=o.created_at,
                    updated_at=o.updated_at,
                )
            )

        return PagedResult[AdminOrderListItem](
            items=items,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def get_order_detail(self, order_id: int) -> AdminOrderDetailResponse:
        stmt = (
            select(Order)
            .join(Customer, Order.customer_id == Customer.id)
            .options(
                joinedload(Order.customer),
                joinedload(Order.items),
                joinedload(Order.payments),
            )
            .where(Order.id == order_id)
        )
        order = self.db.scalar(stmt)
        if not order:
            raise AppError.not_found("Order not found.")

        return self._to_detail(order)

    def change_status(
        self,
        employee_id: int,
        order_id: int,
        next_status: OrderStatus,
        ip: Optional[str] = None,
    ) -> AdminOrderDetailResponse:
        order = self.db.scalar(select(Order).where(Order.id == order_id))
        if not order:
            raise AppError.not_found("Order not found.")

        current = order.status
        allowed = ALLOWED_TRANSITIONS.get(current, [])

        if next_status.value not in allowed:
            raise AppError.bad_request(
                f"Cannot change order status from '{current}' to '{next_status.value}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'None'}."
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        order.status = next_status.value
        order.updated_at = now

        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="Order",
            entity_id=order.id,
            action="ChangeStatus",
            diff={"from": current, "to": next_status.value},
            ip_address=ip,
        )

        self.db.commit()
        return self.get_order_detail(order_id)

    def cancel_order(
        self,
        employee_id: int,
        order_id: int,
        reason: str,
        ip: Optional[str] = None,
    ) -> AdminOrderDetailResponse:
        order = self.db.scalar(select(Order).where(Order.id == order_id))
        if not order:
            raise AppError.not_found("Order not found.")

        # Staff/Managers can cancel up to Preparing (Pending, Confirmed, Preparing)
        cancellable_statuses = [
            OrderStatus.Pending.value,
            OrderStatus.Confirmed.value,
            OrderStatus.Preparing.value,
        ]
        if order.status not in cancellable_statuses:
            raise AppError.conflict(
                f"Order in '{order.status}' status can no longer be cancelled. Allowed: Pending, Confirmed, Preparing."
            )

        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Update order status
        old_status = order.status
        order.status = OrderStatus.Cancelled.value
        order.updated_at = now

        # 2. Restore stock and write Return movements
        items = self.db.scalars(
            select(OrderItem).where(OrderItem.order_id == order_id)
        ).all()

        for item in items:
            self.db.execute(
                update(Inventory)
                .where(Inventory.product_id == item.product_id)
                .values(
                    quantity=Inventory.quantity + item.quantity,
                    updated_at=now,
                )
            )
            self.db.add(
                StockMovement(
                    product_id=item.product_id,
                    employee_id=employee_id,
                    movement_type=StockMovementType.Return.value,
                    quantity=item.quantity,
                    reference_id=order_id,
                    created_at=now,
                )
            )

        # 3. Check payment status
        paid_payment = self.db.scalar(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.Paid.value,
            )
        )

        # Cancel pending payments
        self.db.execute(
            update(Payment)
            .where(Payment.order_id == order_id, Payment.status == PaymentStatus.Pending.value)
            .values(status=PaymentStatus.Cancelled.value)
        )

        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="Order",
            entity_id=order_id,
            action="AdminCancel",
            diff={
                "from_status": old_status,
                "reason": reason,
                "refund_needed": (paid_payment is not None),
            },
            ip_address=ip,
        )

        self.db.commit()
        return self.get_order_detail(order_id)

    def mark_cash_paid(
        self,
        employee_id: int,
        order_id: int,
        ip: Optional[str] = None,
    ) -> AdminOrderDetailResponse:
        order = self.db.scalar(select(Order).where(Order.id == order_id))
        if not order:
            raise AppError.not_found("Order not found.")

        # Payment for CashOnDelivery
        payment = self.db.scalar(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.method == PaymentMethod.CashOnDelivery.value,
            )
        )
        if not payment:
            raise AppError.bad_request("This order is not configured for Cash on Delivery.")

        if payment.status == PaymentStatus.Paid.value:
            raise AppError.conflict("This payment is already recorded as Paid.")

        now = datetime.datetime.now(datetime.timezone.utc)
        payment.status = PaymentStatus.Paid.value
        payment.paid_at = now

        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="Payment",
            entity_id=payment.id,
            action="MarkCashPaid",
            diff={"order_id": order_id, "amount": str(payment.amount)},
            ip_address=ip,
        )

        self.db.commit()
        return self.get_order_detail(order_id)

    def record_refund(
        self,
        employee_id: int,
        order_id: int,
        request: RecordRefundRequest,
        ip: Optional[str] = None,
    ) -> AdminOrderDetailResponse:
        payment = self.db.scalar(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.Paid.value,
            )
        )
        if not payment:
            raise AppError.bad_request("No completed online payment found to refund for this order.")

        now = datetime.datetime.now(datetime.timezone.utc)
        payment.status = PaymentStatus.Refunded.value
        if request.transaction_id:
            payment.transaction_id = request.transaction_id

        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="Payment",
            entity_id=payment.id,
            action="RecordRefund",
            diff={
                "order_id": order_id,
                "refunded_amount": str(request.amount or payment.amount),
                "refund_tx": request.transaction_id,
                "reason": request.reason,
            },
            ip_address=ip,
        )

        self.db.commit()
        return self.get_order_detail(order_id)

    def _to_detail(self, order: Order) -> AdminOrderDetailResponse:
        address_dto = None
        if order.address_snapshot:
            try:
                snap = json.loads(order.address_snapshot)
                address_dto = AddressResponse(
                    address_id=snap.get("address_id", 0),
                    label=snap.get("label", ""),
                    recipient_name=snap.get("recipient_name", ""),
                    phone_number=snap.get("phone_number", ""),
                    address_line=snap.get("address_line", ""),
                    district=snap.get("district"),
                    city=snap.get("city", ""),
                    note=snap.get("note"),
                    latitude=snap.get("latitude"),
                    longitude=snap.get("longitude"),
                    is_default=snap.get("is_default", False),
                )
            except Exception:
                address_dto = None

        if not address_dto and order.address_id:
            addr = self.db.scalar(select(CustomerAddress).where(CustomerAddress.id == order.address_id))
            if addr:
                address_dto = AddressResponse(
                    address_id=addr.id,
                    label=addr.label,
                    recipient_name=addr.recipient_name,
                    phone_number=addr.phone_number,
                    address_line=addr.address_line,
                    district=addr.district,
                    city=addr.city,
                    note=addr.note,
                    latitude=float(addr.latitude) if addr.latitude is not None else None,
                    longitude=float(addr.longitude) if addr.longitude is not None else None,
                    is_default=addr.is_default,
                )

        has_paid_payment = any(p.status == PaymentStatus.Paid.value for p in order.payments)
        refund_needed = (order.status == OrderStatus.Cancelled.value and has_paid_payment)
        can_cancel = order.status in (OrderStatus.Pending.value, OrderStatus.Confirmed.value, OrderStatus.Preparing.value)

        payments_dto = [
            PaymentResponse(
                payment_id=p.id,
                order_id=p.order_id,
                method=PaymentMethod(p.method),
                status=PaymentStatus(p.status),
                amount=p.amount,
                transaction_id=p.transaction_id,
                created_at=p.created_at,
                paid_at=p.paid_at,
            )
            for p in order.payments
        ]

        items_dto = [
            OrderItemResponse(
                product_id=i.product_id,
                product_name=i.product_name,
                unit_price=i.unit_price,
                quantity=i.quantity,
                subtotal=i.subtotal,
            )
            for i in order.items
        ]

        return AdminOrderDetailResponse(
            order_id=order.id,
            customer_id=order.customer_id,
            customer_username=order.customer.username,
            customer_email=order.customer.email,
            customer_phone=order.customer.phone_number,
            status=OrderStatus(order.status),
            subtotal=order.subtotal,
            delivery_fee=order.delivery_fee,
            discount=order.discount,
            total_amount=order.total_amount,
            created_at=order.created_at,
            updated_at=order.updated_at,
            delivery_address=address_dto,
            items=items_dto,
            payments=payments_dto,
            allowed_next_statuses=ALLOWED_TRANSITIONS.get(order.status, []),
            can_cancel=can_cancel,
            refund_needed=refund_needed,
        )

