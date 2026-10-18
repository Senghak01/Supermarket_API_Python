import datetime
import json
from decimal import Decimal
from typing import Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.errors import AppError
from app.models.cart import Cart, CartItem
from app.models.catalog import Category, Inventory, Product
from app.models.customer import CustomerAddress
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.stock_movement import StockMovement, StockMovementType
from app.schemas.address import AddressResponse
from app.schemas.common import PagedResult
from app.schemas.order import (
    OrderDetailResponse,
    OrderItemResponse,
    OrderSummaryResponse,
    PlaceOrderRequest,
)
from app.schemas.payment import PaymentSummaryResponse


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def place_order(self, customer_id: int, request: PlaceOrderRequest) -> OrderDetailResponse:
        # Verify address belongs to customer and is not soft-deleted
        address = self.db.scalar(
            select(CustomerAddress).where(
                CustomerAddress.id == request.address_id,
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.is_deleted.is_(False),
            )
        )
        if not address:
            raise AppError.bad_request("Delivery address not found.")

        # Address snapshot dictionary
        address_snapshot_dict = {
            "address_id": address.id,
            "label": address.label,
            "recipient_name": address.recipient_name,
            "phone_number": address.phone_number,
            "address_line": address.address_line,
            "district": address.district,
            "city": address.city,
            "note": address.note,
            "latitude": float(address.latitude) if address.latitude is not None else None,
            "longitude": float(address.longitude) if address.longitude is not None else None,
            "is_default": address.is_default,
        }
        address_snapshot_json = json.dumps(address_snapshot_dict)

        # Load cart items with products and categories
        cart_items_stmt = (
            select(CartItem)
            .join(Cart, CartItem.cart_id == Cart.id)
            .join(Product, CartItem.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(
                joinedload(CartItem.product).joinedload(Product.category),
                joinedload(CartItem.product).joinedload(Product.inventory),
            )
            .where(Cart.customer_id == customer_id)
            .order_by(CartItem.product_id.asc())  # Fixed lock order avoids deadlocks
        )
        cart_items = self.db.scalars(cart_items_stmt).unique().all()

        if not cart_items:
            raise AppError.bad_request("Your cart is empty.")

        # Check issues (unavailability or out of stock)
        problems = []
        for ci in cart_items:
            stock = (
                ci.product.inventory.quantity
                if (ci.product.is_active and ci.product.category.is_active and ci.product.inventory)
                else 0
            )
            if ci.quantity > stock:
                problems.append(
                    f"{ci.product.name} is unavailable"
                    if stock == 0
                    else f"{ci.product.name} (requested {ci.quantity}, available {stock})"
                )

        if problems:
            details = "; ".join(problems)
            raise AppError.conflict(f"Some items are not available in the requested quantity: {details}.")

        now = datetime.datetime.now(datetime.timezone.utc)

        # Atomic conditional stock deduction per product in ascending product ID order
        for ci in cart_items:
            product_id = ci.product_id
            qty = ci.quantity

            stmt = (
                update(Inventory)
                .where(
                    Inventory.product_id == product_id,
                    Inventory.quantity >= qty,
                )
                .values(
                    quantity=Inventory.quantity - qty,
                    updated_at=now,
                )
            )
            res = self.db.execute(stmt)
            if res.rowcount == 0:
                self.db.rollback()
                raise AppError.conflict(f'"{ci.product.name}" just ran out of stock. Please update your cart.')

        # Calculate totals
        subtotal = sum(ci.product.price * ci.quantity for ci in cart_items)
        delivery_fee = (
            Decimal("0.00")
            if subtotal >= settings.DELIVERY_FREE_THRESHOLD
            else settings.DELIVERY_FLAT_FEE
        )
        discount = Decimal("0.00")
        total_amount = subtotal + delivery_fee - discount

        order = Order(
            customer_id=customer_id,
            address_id=address.id,
            status=OrderStatus.Pending.value,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount=discount,
            total_amount=total_amount,
            address_snapshot=address_snapshot_json,
            created_at=now,
        )
        self.db.add(order)
        self.db.flush()  # assigns order.id

        order_items = [
            OrderItem(
                order_id=order.id,
                product_id=ci.product_id,
                product_name=ci.product.name,
                unit_price=ci.product.price,
                quantity=ci.quantity,
                subtotal=ci.product.price * ci.quantity,
            )
            for ci in cart_items
        ]
        self.db.add_all(order_items)

        # Log negative Sale StockMovements
        stock_movements = [
            StockMovement(
                product_id=ci.product_id,
                movement_type=StockMovementType.Sale.value,
                quantity=-ci.quantity,
                reference_id=order.id,
                created_at=now,
            )
            for ci in cart_items
        ]
        self.db.add_all(stock_movements)

        # Clear cart
        for ci in cart_items:
            self.db.delete(ci)

        self.db.commit()
        self.db.refresh(order)

        return self._to_detail(order)

    def get_all(self, customer_id: int, page: int = 1, page_size: int = 20) -> PagedResult[OrderSummaryResponse]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = select(Order).where(Order.customer_id == customer_id)

        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = self.db.scalar(count_stmt) or 0

        paged_orders_stmt = (
            query
            .options(joinedload(Order.items))
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        orders = self.db.scalars(paged_orders_stmt).unique().all()

        items = [
            OrderSummaryResponse(
                order_id=o.id,
                status=OrderStatus(o.status),
                total_amount=o.total_amount,
                item_count=sum(i.quantity for i in o.items),
                created_at=o.created_at,
            )
            for o in orders
        ]

        return PagedResult[OrderSummaryResponse](
            items=items,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def get_by_id(self, customer_id: int, order_id: int) -> OrderDetailResponse:
        stmt = (
            select(Order)
            .options(
                joinedload(Order.items),
                joinedload(Order.payments),
            )
            .where(Order.id == order_id, Order.customer_id == customer_id)
        )
        order = self.db.scalar(stmt)
        if not order:
            raise AppError.not_found("Order not found.")

        return self._to_detail(order)

    def cancel_order(self, customer_id: int, order_id: int) -> OrderDetailResponse:
        order = self.db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == customer_id))
        if not order:
            raise AppError.not_found("Order not found.")

        # Check if already paid
        paid_payment = self.db.scalar(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.Paid.value,
            )
        )
        if paid_payment:
            raise AppError.conflict("This order is already paid. Please contact support to cancel it and get a refund.")

        success = self._cancel_core(order_id, customer_id=customer_id, pending_only=False)
        if not success:
            raise AppError.conflict("This order can no longer be cancelled.")

        return self.get_by_id(customer_id, order_id)

    def expire_unpaid_orders(self, created_before: datetime.datetime) -> int:
        """Finds orders Pending older than 30 minutes, restores stock, and cancels them."""
        stmt = (
            select(Order.id)
            .where(
                Order.status == OrderStatus.Pending.value,
                Order.created_at < created_before,
            )
            .order_by(Order.id.asc())
            .limit(100)
        )
        order_ids = self.db.scalars(stmt).all()

        cancelled_count = 0
        for oid in order_ids:
            if self._cancel_core(oid, customer_id=None, pending_only=True):
                cancelled_count += 1

        return cancelled_count

    def _cancel_core(self, order_id: int, customer_id: Optional[int], pending_only: bool) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)

        # Conditional update: only Pending (or Confirmed if not pending_only)
        allowed_statuses = [OrderStatus.Pending.value]
        if not pending_only:
            allowed_statuses.append(OrderStatus.Confirmed.value)

        update_stmt = (
            update(Order)
            .where(
                Order.id == order_id,
                Order.status.in_(allowed_statuses),
            )
        )
        if customer_id is not None:
            update_stmt = update_stmt.where(Order.customer_id == customer_id)

        update_stmt = update_stmt.values(
            status=OrderStatus.Cancelled.value,
            updated_at=now,
        )

        res = self.db.execute(update_stmt)
        if res.rowcount == 0:
            return False

        # Restore inventory and write Return stock movements
        items_stmt = (
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.product_id.asc())
        )
        items = self.db.scalars(items_stmt).all()

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
                    movement_type=StockMovementType.Return.value,
                    quantity=item.quantity,
                    reference_id=order_id,
                    created_at=now,
                )
            )

        # Cancel pending payments
        self.db.execute(
            update(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.Pending.value,
            )
            .values(status=PaymentStatus.Cancelled.value)
        )

        self.db.commit()
        return True

    def _to_detail(self, order: Order) -> OrderDetailResponse:
        # Resolve address
        address_dto: Optional[AddressResponse] = None
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

        # Latest non-cancelled payment
        latest_payment = self.db.scalar(
            select(Payment)
            .where(
                Payment.order_id == order.id,
                Payment.status != PaymentStatus.Cancelled.value,
            )
            .order_by(Payment.id.desc())
        )

        payment_summary: Optional[PaymentSummaryResponse] = None
        if latest_payment:
            payment_summary = PaymentSummaryResponse(
                payment_id=latest_payment.id,
                method=PaymentMethod(latest_payment.method),
                status=PaymentStatus(latest_payment.status),
                amount=latest_payment.amount,
                paid_at=latest_payment.paid_at,
            )

        order_status = OrderStatus(order.status)
        is_paid = latest_payment is not None and latest_payment.status == PaymentStatus.Paid.value
        can_cancel = (
            order_status in (OrderStatus.Pending, OrderStatus.Confirmed)
            and not is_paid
        )

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

        return OrderDetailResponse(
            order_id=order.id,
            status=order_status,
            subtotal=order.subtotal,
            delivery_fee=order.delivery_fee,
            discount=order.discount,
            total_amount=order.total_amount,
            created_at=order.created_at,
            updated_at=order.updated_at,
            can_cancel=can_cancel,
            payment=payment_summary,
            delivery_address=address_dto,
            items=items_dto,
        )

