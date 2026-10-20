import datetime
import enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.catalog import Product
    from app.models.employee import Employee


class StockMovementType(str, enum.Enum):
    Purchase = "Purchase"
    Sale = "Sale"
    Return = "Return"
    Adjustment = "Adjustment"


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        index=True,
        nullable=False
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # Signed integer: Sale is negative, Return is positive
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)  # Order ID / Purchase ID
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")
    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="stock_movements")

    __table_args__ = (
        Index("ix_stock_movements_prod_date", "product_id", "created_at"),
    )

