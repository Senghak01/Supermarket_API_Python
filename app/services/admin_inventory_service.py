import datetime
from typing import List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.models.catalog import Category, Inventory, Product
from app.models.employee import Employee
from app.models.stock_movement import StockMovement, StockMovementType
from app.schemas.admin_inventory import (
    InventoryListItem,
    StockAdjustmentRequest,
    StockMovementListItem,
)
from app.schemas.common import PagedResult

LOW_STOCK_THRESHOLD = 10


class AdminInventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_inventory(
        self,
        search: Optional[str] = None,
        low_stock_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[InventoryListItem]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = (
            select(Product)
            .join(Inventory, Product.id == Inventory.product_id)
            .join(Category, Product.category_id == Category.id)
            .options(joinedload(Product.category), joinedload(Product.inventory))
        )

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                (Product.name.ilike(term)) |
                (Product.sku.ilike(term))
            )

        if low_stock_only:
            query = query.where(Inventory.quantity <= LOW_STOCK_THRESHOLD)

        count_query = select(func.count()).select_from(query.with_only_columns(Product.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        paged_query = query.order_by(Inventory.quantity.asc(), Product.id.asc()).offset((page - 1) * page_size).limit(page_size)
        products = self.db.scalars(paged_query).unique().all()

        items = [
            InventoryListItem(
                product_id=p.id,
                name=p.name,
                sku=p.sku,
                category_name=p.category.name if p.category else "",
                quantity=p.inventory.quantity if p.inventory else 0,
                unit=p.unit,
                price=p.price,
                is_active=p.is_active,
                is_low_stock=(p.inventory.quantity <= LOW_STOCK_THRESHOLD if p.inventory else True),
                updated_at=p.inventory.updated_at if p.inventory else p.created_at,
            )
            for p in products
        ]

        return PagedResult[InventoryListItem](
            items=items,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def adjust_stock(
        self,
        employee_id: int,
        request: StockAdjustmentRequest,
        ip: Optional[str] = None,
    ) -> InventoryListItem:
        if request.delta == 0:
            raise AppError.bad_request("Stock delta must be non-zero.")

        product = self.db.scalar(
            select(Product)
            .options(joinedload(Product.category), joinedload(Product.inventory))
            .where(Product.id == request.product_id)
        )
        if not product:
            raise AppError.not_found("Product not found.")

        now = datetime.datetime.now(datetime.timezone.utc)

        # Atomic conditional stock update: ensure stock never goes negative
        stmt = (
            update(Inventory)
            .where(
                Inventory.product_id == request.product_id,
                Inventory.quantity + request.delta >= 0,
            )
            .values(
                quantity=Inventory.quantity + request.delta,
                updated_at=now,
            )
        )
        res = self.db.execute(stmt)
        if res.rowcount == 0:
            current_qty = product.inventory.quantity if product.inventory else 0
            raise AppError.conflict(
                f"Cannot decrease stock by {-request.delta}. Current stock is only {current_qty}."
            )

        # Record StockMovement with employee ID
        movement = StockMovement(
            product_id=product.id,
            employee_id=employee_id,
            movement_type=StockMovementType.Adjustment.value,
            quantity=request.delta,
            reference_id=None,
            created_at=now,
        )
        self.db.add(movement)

        # Record AuditLog
        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="Inventory",
            entity_id=product.id,
            action="AdjustStock",
            diff={
                "product": product.name,
                "delta": request.delta,
                "reason": request.reason.strip(),
            },
            ip_address=ip,
        )

        self.db.commit()
        self.db.refresh(product)

        return InventoryListItem(
            product_id=product.id,
            name=product.name,
            sku=product.sku,
            category_name=product.category.name if product.category else "",
            quantity=product.inventory.quantity if product.inventory else 0,
            unit=product.unit,
            price=product.price,
            is_active=product.is_active,
            is_low_stock=(product.inventory.quantity <= LOW_STOCK_THRESHOLD if product.inventory else True),
            updated_at=product.inventory.updated_at if product.inventory else now,
        )

    def get_movement_history(
        self,
        product_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[StockMovementListItem]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = (
            select(StockMovement)
            .join(Product, StockMovement.product_id == Product.id)
            .outerjoin(Employee, StockMovement.employee_id == Employee.id)
            .options(
                joinedload(StockMovement.product),
                joinedload(StockMovement.employee),
            )
        )

        if product_id is not None:
            query = query.where(StockMovement.product_id == product_id)

        count_query = select(func.count()).select_from(query.with_only_columns(StockMovement.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        paged_query = query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).offset((page - 1) * page_size).limit(page_size)
        movements = self.db.scalars(paged_query).unique().all()

        items = [
            StockMovementListItem(
                id=m.id,
                product_id=m.product_id,
                product_name=m.product.name if m.product else "",
                employee_id=m.employee_id,
                employee_name=(
                    f"{m.employee.first_name or ''} {m.employee.last_name or ''}".strip() or m.employee.username
                    if m.employee
                    else "System / Checkout"
                ),
                movement_type=m.movement_type,
                quantity=m.quantity,
                reference_id=m.reference_id,
                created_at=m.created_at,
            )
            for m in movements
        ]

        return PagedResult[StockMovementListItem](
            items=items,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

