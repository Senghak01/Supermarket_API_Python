from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload
from app.core.errors import AppError
from app.models.catalog import Category, Inventory, Product
from app.schemas.catalog import CategoryResponse, ProductDetailResponse, ProductListItem
from app.schemas.common import PagedResult


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_categories(self) -> List[CategoryResponse]:
        # Count active products per category
        stmt = (
            select(
                Category,
                func.count(Product.id).filter(Product.is_active.is_(True)).label("product_count")
            )
            .outerjoin(Product, Product.category_id == Category.id)
            .where(Category.is_active.is_(True))
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

    def get_category(self, category_id: int) -> CategoryResponse:
        stmt = (
            select(
                Category,
                func.count(Product.id).filter(Product.is_active.is_(True)).label("product_count")
            )
            .outerjoin(Product, Product.category_id == Category.id)
            .where(Category.id == category_id, Category.is_active.is_(True))
            .group_by(Category.id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            raise AppError.not_found("Category not found.")

        cat, prod_count = row
        return CategoryResponse(
            category_id=cat.id,
            name=cat.name,
            description=cat.description,
            image_url=cat.image_url,
            product_count=prod_count,
        )

    def search_products(
        self,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        in_stock_only: bool = False,
        sort: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedResult[ProductListItem]:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise AppError.bad_request("MinPrice cannot be greater than MaxPrice.")

        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)

        # Base query: only active products in active categories
        query = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(joinedload(Product.category), joinedload(Product.inventory))
            .where(Product.is_active.is_(True), Category.is_active.is_(True))
        )

        if search and search.strip():
            term = f"%{search.strip()}%"
            exact_term = search.strip()
            query = query.where(
                (Product.name.ilike(term)) |
                (Product.sku == exact_term) |
                (Product.description.ilike(term))
            )

        if category_id is not None:
            query = query.where(Product.category_id == category_id)

        if min_price is not None:
            query = query.where(Product.price >= min_price)

        if max_price is not None:
            query = query.where(Product.price <= max_price)

        if in_stock_only:
            query = query.where(Inventory.quantity > 0)

        # Sort with Product.id as tie-breaker
        if sort == "price_asc":
            query = query.order_by(Product.price.asc(), Product.id.asc())
        elif sort == "price_desc":
            query = query.order_by(Product.price.desc(), Product.id.asc())
        elif sort == "newest":
            query = query.order_by(Product.created_at.desc(), Product.id.asc())
        else:
            query = query.order_by(Product.name.asc(), Product.id.asc())

        # Count total
        count_query = select(func.count()).select_from(query.with_only_columns(Product.id).subquery())
        total_count = self.db.scalar(count_query) or 0

        # Paged items
        items_query = query.offset((page - 1) * page_size).limit(page_size)
        products = self.db.scalars(items_query).unique().all()

        item_responses = [
            ProductListItem(
                product_id=p.id,
                name=p.name,
                sku=p.sku,
                price=p.price,
                unit=p.unit,
                image_url=p.image_url,
                category_id=p.category_id,
                category_name=p.category.name if p.category else "",
                in_stock=(p.inventory is not None and p.inventory.quantity > 0),
            )
            for p in products
        ]

        return PagedResult[ProductListItem](
            items=item_responses,
            page=page,
            page_size=page_size,
            total_count=total_count,
        )

    def get_product(self, product_id: int) -> ProductDetailResponse:
        stmt = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(joinedload(Product.category), joinedload(Product.inventory))
            .where(
                Product.id == product_id,
                Product.is_active.is_(True),
                Category.is_active.is_(True)
            )
        )
        product = self.db.scalar(stmt)
        if not product:
            raise AppError.not_found("Product not found.")

        stock_qty = product.inventory.quantity if product.inventory else 0

        return ProductDetailResponse(
            product_id=product.id,
            name=product.name,
            sku=product.sku,
            price=product.price,
            unit=product.unit,
            image_url=product.image_url,
            category_id=product.category_id,
            category_name=product.category.name if product.category else "",
            in_stock=stock_qty > 0,
            description=product.description,
            stock_quantity=stock_qty,
        )

