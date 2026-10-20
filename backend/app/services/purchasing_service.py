import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.models.catalog import Inventory, Product
from app.models.employee import Employee
from app.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseStatus,
    Supplier,
)
from app.models.stock_movement import StockMovement, StockMovementType
from app.schemas.common import PagedResult
from app.schemas.purchasing import (
    PurchaseOrderCreateRequest,
    PurchaseOrderItemResponse,
    PurchaseOrderResponse,
    SupplierCreateRequest,
    SupplierResponse,
    SupplierUpdateRequest,
)


class PurchasingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Suppliers ---

    def list_suppliers(self, active_only: bool = False) -> List[SupplierResponse]:
        query = select(Supplier).order_by(Supplier.name.asc())
        if active_only:
            query = query.where(Supplier.is_active.is_(True))
        suppliers = self.db.scalars(query).all()
        return [
            SupplierResponse(
                id=s.id,
                name=s.name,
                contact_name=s.contact_name,
                email=s.email,
                phone=s.phone,
                address=s.address,
                is_active=s.is_active,
                created_at=s.created_at,
            )
            for s in suppliers
        ]

    def create_supplier(self, employee_id: int, request: SupplierCreateRequest, ip: Optional[str] = None) -> SupplierResponse:
        name = request.name.strip()
        existing = self.db.scalar(select(Supplier).where(Supplier.name == name))
        if existing:
            raise AppError.conflict(f"Supplier '{name}' already exists.")

        supplier = Supplier(
            name=name,
            contact_name=request.contact_name.strip() if request.contact_name else None,
            email=request.email.strip().lower() if request.email else None,
            phone=request.phone.strip() if request.phone else None,
            address=request.address.strip() if request.address else None,
            is_active=request.is_active,
        )
        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)

        record_audit_log(self.db, employee_id, "Supplier", supplier.id, "Create", {"name": supplier.name}, ip)
        self.db.commit()

        return SupplierResponse(
            id=supplier.id,
            name=supplier.name,
            contact_name=supplier.contact_name,
            email=supplier.email,
            phone=supplier.phone,
            address=supplier.address,
            is_active=supplier.is_active,
            created_at=supplier.created_at,
        )

    def update_supplier(self, employee_id: int, supplier_id: int, request: SupplierUpdateRequest, ip: Optional[str] = None) -> SupplierResponse:
        supplier = self.db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise AppError.not_found("Supplier not found.")

        old_name = supplier.name
        if request.name is not None:
            new_name = request.name.strip()
            if new_name != supplier.name:
                existing = self.db.scalar(select(Supplier).where(Supplier.name == new_name))
                if existing:
                    raise AppError.conflict(f"Supplier '{new_name}' already exists.")
                supplier.name = new_name

        if request.contact_name is not None:
            supplier.contact_name = request.contact_name.strip() or None
        if request.email is not None:
            supplier.email = request.email.strip().lower() or None
        if request.phone is not None:
            supplier.phone = request.phone.strip() or None
        if request.address is not None:
            supplier.address = request.address.strip() or None
        if request.is_active is not None:
            supplier.is_active = request.is_active

        supplier.updated_at = datetime.datetime.now(datetime.timezone.utc)
        record_audit_log(self.db, employee_id, "Supplier", supplier.id, "Update", {"old_name": old_name, "name": supplier.name}, ip)
        self.db.commit()
        self.db.refresh(supplier)

        return SupplierResponse(
            id=supplier.id,
            name=supplier.name,
            contact_name=supplier.contact_name,
            email=supplier.email,
            phone=supplier.phone,
            address=supplier.address,
            is_active=supplier.is_active,
            created_at=supplier.created_at,
        )

    # --- Purchase Orders ---

    def list_purchases(
        self,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[PurchaseOrderResponse]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = (
            select(PurchaseOrder)
            .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
            .join(Employee, PurchaseOrder.employee_id == Employee.id)
            .options(
                joinedload(PurchaseOrder.supplier),
                joinedload(PurchaseOrder.employee),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
            )
        )

        if supplier_id:
            query = query.where(PurchaseOrder.supplier_id == supplier_id)
        if status:
            query = query.where(PurchaseOrder.status == status)

        count_query = select(func.count()).select_from(query.with_only_columns(PurchaseOrder.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        paged_query = query.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        purchases = self.db.scalars(paged_query).unique().all()

        return PagedResult[PurchaseOrderResponse](
            items=[self._to_response(po) for po in purchases],
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def get_purchase(self, purchase_id: int) -> PurchaseOrderResponse:
        stmt = (
            select(PurchaseOrder)
            .options(
                joinedload(PurchaseOrder.supplier),
                joinedload(PurchaseOrder.employee),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
            )
            .where(PurchaseOrder.id == purchase_id)
        )
        po = self.db.scalar(stmt)
        if not po:
            raise AppError.not_found("Purchase order not found.")
        return self._to_response(po)

    def create_purchase(self, employee_id: int, request: PurchaseOrderCreateRequest, ip: Optional[str] = None) -> PurchaseOrderResponse:
        supplier = self.db.scalar(select(Supplier).where(Supplier.id == request.supplier_id))
        if not supplier:
            raise AppError.bad_request("Supplier not found.")

        # Calculate totals & prepare items
        total_amount = Decimal("0.00")
        items_to_add = []

        for item_in in request.items:
            product = self.db.scalar(select(Product).where(Product.id == item_in.product_id))
            if not product:
                raise AppError.bad_request(f"Product ID {item_in.product_id} not found.")

            subtotal = item_in.unit_cost * item_in.quantity
            total_amount += subtotal

            items_to_add.append(
                PurchaseOrderItem(
                    product_id=product.id,
                    unit_cost=item_in.unit_cost,
                    quantity=item_in.quantity,
                    received_quantity=0,
                    subtotal=subtotal,
                )
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        purchase = PurchaseOrder(
            supplier_id=supplier.id,
            employee_id=employee_id,
            status=PurchaseStatus.Ordered.value,
            total_amount=total_amount,
            invoice_number=request.invoice_number.strip() if request.invoice_number else None,
            notes=request.notes.strip() if request.notes else None,
            ordered_at=now,
            items=items_to_add,
        )
        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)

        record_audit_log(
            self.db,
            employee_id,
            "PurchaseOrder",
            purchase.id,
            "Create",
            {"supplier": supplier.name, "total": str(total_amount), "items_count": len(items_to_add)},
            ip,
        )
        self.db.commit()

        return self.get_purchase(purchase.id)

    def receive_stock(self, employee_id: int, purchase_id: int, ip: Optional[str] = None) -> PurchaseOrderResponse:
        stmt = (
            select(PurchaseOrder)
            .options(
                joinedload(PurchaseOrder.supplier),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
            )
            .where(PurchaseOrder.id == purchase_id)
        )
        purchase = self.db.scalar(stmt)
        if not purchase:
            raise AppError.not_found("Purchase order not found.")

        if purchase.status == PurchaseStatus.Received.value:
            raise AppError.conflict("This purchase order has already been received.")

        if purchase.status == PurchaseStatus.Cancelled.value:
            raise AppError.conflict("Cannot receive stock for a cancelled purchase order.")

        now = datetime.datetime.now(datetime.timezone.utc)

        # For each item, increase inventory and write Purchase StockMovement
        for item in purchase.items:
            qty = item.quantity
            self.db.execute(
                update(Inventory)
                .where(Inventory.product_id == item.product_id)
                .values(
                    quantity=Inventory.quantity + qty,
                    updated_at=now,
                )
            )

            # Record StockMovement
            movement = StockMovement(
                product_id=item.product_id,
                employee_id=employee_id,
                movement_type=StockMovementType.Purchase.value,
                quantity=qty,
                reference_id=purchase.id,
                created_at=now,
            )
            self.db.add(movement)
            item.received_quantity = qty

        purchase.status = PurchaseStatus.Received.value
        purchase.received_at = now
        purchase.updated_at = now

        record_audit_log(
            self.db,
            employee_id,
            "PurchaseOrder",
            purchase.id,
            "ReceiveStock",
            {"total_items": len(purchase.items), "received_at": str(now)},
            ip,
        )

        self.db.commit()
        return self.get_purchase(purchase_id)

    def _to_response(self, po: PurchaseOrder) -> PurchaseOrderResponse:
        emp_name = (
            f"{po.employee.first_name or ''} {po.employee.last_name or ''}".strip()
            or po.employee.username
        )
        items_dto = [
            PurchaseOrderItemResponse(
                id=i.id,
                product_id=i.product_id,
                product_name=i.product.name if i.product else "",
                sku=i.product.sku if i.product else "",
                unit_cost=i.unit_cost,
                quantity=i.quantity,
                received_quantity=i.received_quantity,
                subtotal=i.subtotal,
            )
            for i in po.items
        ]
        return PurchaseOrderResponse(
            id=po.id,
            supplier_id=po.supplier_id,
            supplier_name=po.supplier.name if po.supplier else "",
            employee_id=po.employee_id,
            employee_name=emp_name,
            status=PurchaseStatus(po.status),
            total_amount=po.total_amount,
            invoice_number=po.invoice_number,
            notes=po.notes,
            ordered_at=po.ordered_at,
            received_at=po.received_at,
            created_at=po.created_at,
            items=items_dto,
        )

