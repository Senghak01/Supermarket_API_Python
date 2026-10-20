import datetime
from decimal import Decimal
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from app.core.errors import AppError
from app.models.cart import Cart, CartItem
from app.models.catalog import Category, Inventory, Product
from app.schemas.cart import (
    MAX_CART_QUANTITY_PER_ITEM,
    AddCartItemRequest,
    CartItemResponse,
    CartResponse,
    UpdateCartItemRequest,
)


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_cart(self, customer_id: int) -> CartResponse:
        # Inactive products are included on purpose so the customer can see and remove them
        stmt = (
            select(CartItem)
            .join(Cart, CartItem.cart_id == Cart.id)
            .join(Product, CartItem.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(
                joinedload(CartItem.product).joinedload(Product.category),
                joinedload(CartItem.product).joinedload(Product.inventory),
            )
            .where(Cart.customer_id == customer_id)
            .order_by(CartItem.id.asc())
        )
        cart_items = self.db.scalars(stmt).unique().all()

        items: list[CartItemResponse] = []
        for ci in cart_items:
            stock = ci.product.inventory.quantity if ci.product.inventory else 0
            is_active = ci.product.is_active and ci.product.category.is_active
            unit_price = ci.product.price
            line_total = unit_price * ci.quantity
            can_checkout = is_active and ci.quantity <= stock

            items.append(
                CartItemResponse(
                    cart_item_id=ci.id,
                    product_id=ci.product_id,
                    name=ci.product.name,
                    sku=ci.product.sku,
                    unit=ci.product.unit,
                    image_url=ci.product.image_url,
                    unit_price=unit_price,
                    quantity=ci.quantity,
                    line_total=line_total,
                    available_quantity=stock,
                    is_available=is_active,
                    can_checkout=can_checkout,
                )
            )

        item_count = sum(i.quantity for i in items)
        subtotal = sum(i.line_total for i in items if i.can_checkout)
        has_issues = any(not i.can_checkout for i in items)

        return CartResponse(
            items=items,
            item_count=item_count,
            subtotal=subtotal,
            has_issues=has_issues,
        )

    def add_item(self, customer_id: int, request: AddCartItemRequest) -> CartResponse:
        stmt = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(joinedload(Product.category), joinedload(Product.inventory))
            .where(
                Product.id == request.product_id,
                Product.is_active.is_(True),
                Category.is_active.is_(True),
            )
        )
        product = self.db.scalar(stmt)
        if not product:
            raise AppError.not_found("Product not found.")

        stock = product.inventory.quantity if product.inventory else 0
        cart = self._get_or_create_cart(customer_id)

        item = self.db.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.product_id == product.id,
            )
        )

        new_quantity = (item.quantity if item else 0) + request.quantity

        if new_quantity > MAX_CART_QUANTITY_PER_ITEM:
            raise AppError.bad_request(f"You can add up to {MAX_CART_QUANTITY_PER_ITEM} of the same product.")

        if new_quantity > stock:
            raise AppError.conflict(f"Not enough stock. Available: {stock}.")

        if item is None:
            item = CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=new_quantity,
            )
            self.db.add(item)
        else:
            item.quantity = new_quantity

        cart.updated_at = datetime.datetime.now(datetime.timezone.utc)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AppError.conflict("The cart was changed by another request. Please try again.")

        return self.get_cart(customer_id)

    def update_item(self, customer_id: int, cart_item_id: int, request: UpdateCartItemRequest) -> CartResponse:
        stmt = (
            select(CartItem)
            .join(Cart, CartItem.cart_id == Cart.id)
            .join(Product, CartItem.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .outerjoin(Inventory, Product.id == Inventory.product_id)
            .options(
                joinedload(CartItem.cart),
                joinedload(CartItem.product).joinedload(Product.category),
                joinedload(CartItem.product).joinedload(Product.inventory),
            )
            .where(CartItem.id == cart_item_id, Cart.customer_id == customer_id)
        )
        item = self.db.scalar(stmt)
        if not item:
            raise AppError.not_found("Cart item not found.")

        if not item.product.is_active or not item.product.category.is_active:
            raise AppError.conflict("This product is no longer available. Remove it from your cart.")

        stock = item.product.inventory.quantity if item.product.inventory else 0
        if request.quantity > stock:
            raise AppError.conflict(f"Not enough stock. Available: {stock}.")

        item.quantity = request.quantity
        item.cart.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()

        return self.get_cart(customer_id)

    def remove_item(self, customer_id: int, cart_item_id: int) -> CartResponse:
        stmt = (
            select(CartItem)
            .join(Cart, CartItem.cart_id == Cart.id)
            .where(CartItem.id == cart_item_id, Cart.customer_id == customer_id)
        )
        item = self.db.scalar(stmt)
        if not item:
            raise AppError.not_found("Cart item not found.")

        cart = self.db.scalar(select(Cart).where(Cart.customer_id == customer_id))
        if cart:
            cart.updated_at = datetime.datetime.now(datetime.timezone.utc)

        self.db.delete(item)
        self.db.commit()

        return self.get_cart(customer_id)

    def clear(self, customer_id: int) -> None:
        cart = self.db.scalar(select(Cart).where(Cart.customer_id == customer_id))
        if cart:
            self.db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
            cart.updated_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

    def _get_or_create_cart(self, customer_id: int) -> Cart:
        cart = self.db.scalar(select(Cart).where(Cart.customer_id == customer_id))
        if cart:
            return cart

        cart = Cart(customer_id=customer_id)
        self.db.add(cart)
        try:
            self.db.commit()
            self.db.refresh(cart)
            return cart
        except IntegrityError:
            self.db.rollback()
            return self.db.scalar(select(Cart).where(Cart.customer_id == customer_id))

