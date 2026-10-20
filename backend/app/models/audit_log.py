import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    entity_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON or descriptive text
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
        nullable=False,
    )

    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_name", "entity_id"),
    )

