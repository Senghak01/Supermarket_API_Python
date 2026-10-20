from decimal import Decimal
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.models.customer import Customer, CustomerAddress
from app.models.order import Order, OrderStatus
from app.schemas.address import AddressResponse
from app.schemas.admin_customer import (
    AdminCustomerDetailResponse,
    AdminCustomerListItem,
)
from app.schemas.common import PagedResult
from app.schemas.order import OrderSummaryResponse


class AdminCustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_customers(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[AdminCustomerListItem]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = select(Customer)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                (Customer.username.ilike(term)) |
                (Customer.email.ilike(term)) |
                (Customer.phone_number.ilike(term))
            )

        if is_active is not None:
            query = query.where(Customer.is_active.is_(is_active))

        count_query = select(func.count()).select_from(query.with_only_columns(Customer.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        paged_query = query.order_by(Customer.id.desc()).offset((page - 1) * page_size).limit(page_size)
        customers = self.db.scalars(paged_query).all()

        items = []
        for c in customers:
            # Aggregate orders
            order_stats = self.db.execute(
                select(
                    func.count(Order.id).label("cnt"),
                    func.coalesce(func.sum(Order.total_amount), Decimal("0.00")).label("total"),
                )
                .where(Order.customer_id == c.id, Order.status != OrderStatus.Cancelled.value)
            ).first()

            cnt = order_stats.cnt if order_stats else 0
            tot = order_stats.total if order_stats else Decimal("0.00")

            items.append(
                AdminCustomerListItem(
                    id=c.id,
                    username=c.username,
                    email=c.email,
                    first_name=c.first_name,
                    last_name=c.last_name,
                    phone_number=c.phone_number,
                    is_active=c.is_active,
                    orders_count=cnt,
                    total_spent=tot,
                    created_at=c.created_at,
                )
            )

        return PagedResult[AdminCustomerListItem](
            items=items,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def get_customer_detail(self, customer_id: int) -> AdminCustomerDetailResponse:
        customer = self.db.scalar(select(Customer).where(Customer.id == customer_id))
        if not customer:
            raise AppError.not_found("Customer not found.")

        # Load addresses
        addresses = self.db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == customer_id, CustomerAddress.is_deleted.is_(False))
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc())
        ).all()

        addr_dtos = [
            AddressResponse(
                address_id=a.id,
                label=a.label,
                recipient_name=a.recipient_name,
                phone_number=a.phone_number,
                address_line=a.address_line,
                district=a.district,
                city=a.city,
                note=a.note,
                latitude=float(a.latitude) if a.latitude is not None else None,
                longitude=float(a.longitude) if a.longitude is not None else None,
                is_default=a.is_default,
            )
            for a in addresses
        ]

        # Recent orders
        orders = self.db.scalars(
            select(Order)
            .options(joinedload(Order.items))
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(10)
        ).unique().all()

        recent_order_dtos = [
            OrderSummaryResponse(
                order_id=o.id,
                status=OrderStatus(o.status),
                total_amount=o.total_amount,
                item_count=sum(i.quantity for i in o.items),
                created_at=o.created_at,
            )
            for o in orders
        ]

        return AdminCustomerDetailResponse(
            id=customer.id,
            username=customer.username,
            email=customer.email,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone_number=customer.phone_number,
            photo_url=customer.photo_url,
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            addresses=addr_dtos,
            recent_orders=recent_order_dtos,
        )

    def toggle_customer_status(
        self,
        employee_id: int,
        customer_id: int,
        is_active: bool,
        ip: Optional[str] = None,
    ) -> AdminCustomerDetailResponse:
        customer = self.db.scalar(select(Customer).where(Customer.id == customer_id))
        if not customer:
            raise AppError.not_found("Customer not found.")

        old_status = customer.is_active
        customer.is_active = is_active
        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="Customer",
            entity_id=customer_id,
            action="ToggleStatus",
            diff={"from": old_status, "to": is_active},
            ip_address=ip,
        )
        self.db.commit()
        return self.get_customer_detail(customer_id)

