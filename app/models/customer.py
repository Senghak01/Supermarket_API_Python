import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.cart import Cart
    from app.models.order import Order


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Social login fields (postponed feature, schema ready)
    provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Profile fields
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_customer_provider_provider_id"),
    )

    # Relationships
    addresses: Mapped[List["CustomerAddress"]] = relationship(
        "CustomerAddress",
        back_populates="customer",
        cascade="all, delete-orphan",
        order_by="desc(CustomerAddress.is_default), desc(CustomerAddress.id)"
    )
    cart: Mapped[Optional["Cart"]] = relationship("Cart", back_populates="customer", uselist=False)
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer")


class CustomerAddress(Base, TimestampMixin):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False)
    
    label: Mapped[str] = mapped_column(String(30), nullable=False)  # Home, Work, etc.
    recipient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False)
    address_line: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Soft delete

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="addresses")

    __table_args__ = (
        Index("ix_customer_addresses_customer_active", "customer_id", "is_deleted"),
    )
