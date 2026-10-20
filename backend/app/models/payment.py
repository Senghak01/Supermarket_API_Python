import datetime
import enum
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order


class PaymentMethod(str, enum.Enum):
    CashOnDelivery = "CashOnDelivery"
    Khqr = "Khqr"
    Card = "Card"


class PaymentStatus(str, enum.Enum):
    Pending = "Pending"
    Paid = "Paid"
    Failed = "Failed"
    Cancelled = "Cancelled"
    Refunded = "Refunded"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default=PaymentStatus.Pending.value,
        index=True,
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True
    )
    paid_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_order_status", "order_id", "status"),
    )

