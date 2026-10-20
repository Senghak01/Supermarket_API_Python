import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.stock_movement import StockMovement
    from app.models.audit_log import AuditLog
    from app.models.purchasing import PurchaseOrder


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)  # Admin, Manager, Staff
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="role")


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="employees")
    refresh_tokens: Mapped[List["EmployeeRefreshToken"]] = relationship(
        "EmployeeRefreshToken",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    stock_movements: Mapped[List["StockMovement"]] = relationship("StockMovement", back_populates="employee")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="employee")
    purchases: Mapped[List["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="employee")


class EmployeeRefreshToken(Base):
    __tablename__ = "employee_refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="refresh_tokens")

