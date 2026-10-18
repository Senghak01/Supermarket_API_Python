import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.models.catalog import Category, Inventory, Product
from app.models.stock_movement import StockMovement, StockMovementType
from app.schemas.admin_catalog import (
    AdminProductListItem,
    CreateCategoryRequest,
    CreateProductRequest,
    UpdateCategoryRequest,
    UpdateProductRequest,
)
from app.schemas.catalog import CategoryResponse
from app.schemas.common import PagedResult


class AdminCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Categories ---

    def list_categories(self) -> List[CategoryResponse]:
        stmt = (
            select(
                Category,
                func.count(Product.id).label("product_count")
            )
            .outerjoin(Product, Product.category_id == Category.id)
            .group_by(Category.id)
            .order_by(Category.name.asc())
        )
        rows = self.db.execute(stmt).all()
        return [
            CategoryResponse(
                category_id=cat.id,
                name=cat.name,
                description=cat.description,
                image_url=cat.image_url,
                product_count=prod_count,
            )
            for cat, prod_count in rows
        ]

    def create_category(self, employee_id: int, request: CreateCategoryRequest, ip: Optional[str] = None) -> CategoryResponse:
        name = request.name.strip()
        existing = self.db.scalar(select(Category).where(Category.name == name))
        if existing:
            raise AppError.conflict(f"Category '{name}' already exists.")

        cat = Category(
            name=name,
            description=request.description.strip() if request.description else None,
            image_url=request.image_url.strip() if request.image_url else None,
            is_active=request.is_active,
        )
        self.db.add(cat)
        self.db.commit()
        self.db.refresh(cat)

        record_audit_log(self.db, employee_id, "Category", cat.id, "Create", {"name": cat.name}, ip)
        self.db.commit()

        return CategoryResponse(
            category_id=cat.id,
            name=cat.name,
            description=cat.description,
            image_url=cat.image_url,
            product_count=0,
        )

    def update_category(self, employee_id: int, category_id: int, request: UpdateCategoryRequest, ip: Optional[str] = None) -> CategoryResponse:
        cat = self.db.scalar(select(Category).where(Category.id == category_id))
        if not cat:
            raise AppError.not_found("Category not found.")

        old_data = {"name": cat.name, "is_active": cat.is_active}

        if request.name is not None:
            new_name = request.name.strip()
            if new_name != cat.name:
                existing = self.db.scalar(select(Category).where(Category.name == new_name))
                if existing:
                    raise AppError.conflict(f"Category '{new_name}' already exists.")
                cat.name = new_name

        if request.description is not None:
            cat.description = request.description.strip() or None
        if request.image_url is not None:
            cat.image_url = request.image_url.strip() or None
        if request.is_active is not None:
            cat.is_active = request.is_active

        self.db.commit()
        record_audit_log(self.db, employee_id, "Category", cat.id, "Update", {"old": old_data, "new": {"name": cat.name, "is_active": cat.is_active}}, ip)
        self.db.commit()

        count = self.db.scalar(select(func.count(Product.id)).where(Product.category_id == cat.id)) or 0
        return CategoryResponse(
            category_id=cat.id,
            name=cat.name,
            description=cat.description,
            image_url=cat.image_url,
            product_count=count,
        )

    # --- Products ---

    def list_products(
        self,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[AdminProductListItem]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        query = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(joinedload(Product.category), joinedload(Product.inventory))
        )

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                (Product.name.ilike(term)) |
                (Product.sku.ilike(term)) |
                (Product.description.ilike(term))
            )

        if category_id is not None:
            query = query.where(Product.category_id == category_id)

        if is_active is not None:
            query = query.where(Product.is_active.is_(is_active))

        count_query = select(func.count()).select_from(query.with_only_columns(Product.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        paged_query = query.order_by(Product.id.desc()).offset((page - 1) * page_size).limit(page_size)
        products = self.db.scalars(paged_query).unique().all()

        items = [
            AdminProductListItem(
                product_id=p.id,
                name=p.name,
                sku=p.sku,
                price=p.price,
                unit=p.unit,
                image_url=p.image_url,
                category_id=p.category_id,
                category_name=p.category.name if p.category else "",
                stock_quantity=p.inventory.quantity if p.inventory else 0,
                is_active=p.is_active,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in products
        ]

        return PagedResult[AdminProductListItem](
            items=items,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def create_product(self, employee_id: int, request: CreateProductRequest, ip: Optional[str] = None) -> AdminProductListItem:
        sku = request.sku.strip().upper()
        existing = self.db.scalar(select(Product).where(Product.sku == sku))
        if existing:
            raise AppError.conflict(f"Product with SKU '{sku}' already exists.")

        category = self.db.scalar(select(Category).where(Category.id == request.category_id))
        if not category:
            raise AppError.bad_request("Category not found.")

        product = Product(
            category_id=category.id,
            name=request.name.strip(),
            sku=sku,
            price=request.price,
            unit=request.unit.strip(),
            description=request.description.strip() if request.description else None,
            image_url=request.image_url.strip() if request.image_url else None,
            is_active=request.is_active,
        )
        self.db.add(product)
        self.db.flush()

        # Create inventory
        inventory = Inventory(
            product_id=product.id,
            quantity=request.initial_stock,
        )
        self.db.add(inventory)

        now = datetime.datetime.now(datetime.timezone.utc)
        if request.initial_stock > 0:
            movement = StockMovement(
                product_id=product.id,
                employee_id=employee_id,
                movement_type=StockMovementType.Adjustment.value,
                quantity=request.initial_stock,
                reference_id=None,
                created_at=now,
            )
            self.db.add(movement)

        record_audit_log(self.db, employee_id, "Product", product.id, "Create", {"sku": product.sku, "name": product.name, "price": str(product.price)}, ip)
        self.db.commit()
        self.db.refresh(product)

        return AdminProductListItem(
            product_id=product.id,
            name=product.name,
            sku=product.sku,
            price=product.price,
            unit=product.unit,
            image_url=product.image_url,
            category_id=category.id,
            category_name=category.name,
            stock_quantity=request.initial_stock,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

    def update_product(self, employee_id: int, product_id: int, request: UpdateProductRequest, ip: Optional[str] = None) -> AdminProductListItem:
        stmt = (
            select(Product)
            .options(joinedload(Product.category), joinedload(Product.inventory))
            .where(Product.id == product_id)
        )
        product = self.db.scalar(stmt)
        if not product:
            raise AppError.not_found("Product not found.")

        old_state = {"price": str(product.price), "is_active": product.is_active, "name": product.name}

        if request.category_id is not None:
            cat = self.db.scalar(select(Category).where(Category.id == request.category_id))
            if not cat:
                raise AppError.bad_request("Category not found.")
            product.category_id = cat.id

        if request.sku is not None:
            new_sku = request.sku.strip().upper()
            if new_sku != product.sku:
                existing = self.db.scalar(select(Product).where(Product.sku == new_sku))
                if existing:
                    raise AppError.conflict(f"Product with SKU '{new_sku}' already exists.")
                product.sku = new_sku

        if request.name is not None:
            product.name = request.name.strip()
        if request.price is not None:
            product.price = request.price
        if request.unit is not None:
            product.unit = request.unit.strip()
        if request.description is not None:
            product.description = request.description.strip() or None
        if request.image_url is not None:
            product.image_url = request.image_url.strip() or None
        if request.is_active is not None:
            product.is_active = request.is_active

        product.updated_at = datetime.datetime.now(datetime.timezone.utc)
        record_audit_log(self.db, employee_id, "Product", product.id, "Update", {"old": old_state, "new": {"price": str(product.price), "is_active": product.is_active}}, ip)
        self.db.commit()
        self.db.refresh(product)

        return AdminProductListItem(
            product_id=product.id,
            name=product.name,
            sku=product.sku,
            price=product.price,
            unit=product.unit,
            image_url=product.image_url,
            category_id=product.category_id,
            category_name=product.category.name if product.category else "",
            stock_quantity=product.inventory.quantity if product.inventory else 0,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

