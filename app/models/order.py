import enum
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.customer import CustomerAddress
    from app.models.catalog import Product
    from app.models.payment import Payment


class OrderStatus(str, enum.Enum):
    Pending = "Pending"
    Confirmed = "Confirmed"
    Preparing = "Preparing"
    ReadyForDelivery = "ReadyForDelivery"
    OutForDelivery = "OutForDelivery"
    Delivered = "Delivered"
    Cancelled = "Cancelled"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
        nullable=False
    )
    address_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customer_addresses.id", ondelete="SET NULL"),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=OrderStatus.Pending.value,
        index=True,
        nullable=False
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Address snapshot in JSON format to guarantee historical accuracy even if customer changes address
    address_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        order_by="desc(Payment.id)"
    )

    __table_args__ = (
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        Index("ix_orders_status", "status"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")

