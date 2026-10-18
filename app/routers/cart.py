from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from app.core.deps import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.cart import AddCartItemRequest, CartResponse, UpdateCartItemRequest
from app.services.cart_service import CartService

router = APIRouter(prefix="/api/cart", tags=["Cart"])


@router.get("", response_model=CartResponse)
def get_cart(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CartService(db)
    return service.get_cart(customer.id)


@router.post("/items", response_model=CartResponse)
def add_item_to_cart(
    body: AddCartItemRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CartService(db)
    return service.add_item(customer.id, body)


@router.put("/items/{cart_item_id}", response_model=CartResponse)
def update_cart_item(
    cart_item_id: int,
    body: UpdateCartItemRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CartService(db)
    return service.update_item(customer.id, cart_item_id, body)


@router.delete("/items/{cart_item_id}", response_model=CartResponse)
def remove_cart_item(
    cart_item_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CartService(db)
    return service.remove_item(customer.id, cart_item_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CartService(db)
    service.clear(customer.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

