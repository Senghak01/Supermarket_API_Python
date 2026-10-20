import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models.catalog import Inventory, Product
from app.models.stock_movement import StockMovement, StockMovementType


def setup_customer_and_address(client: TestClient) -> tuple[str, int]:
    unique_email = f"order_{uuid.uuid4().hex[:8]}@test.com"
    reg = client.post(
        "/api/auth/register",
        json={"username": "orderuser", "email": unique_email, "password": "Password123!"},
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    addr = client.post(
        "/api/addresses",
        json={
            "label": "Home",
            "recipientName": "Order User",
            "phoneNumber": "+85599887766",
            "addressLine": "Street 2004",
            "city": "Phnom Penh",
            "isDefault": True,
        },
        headers=headers,
    )
    return token, addr.json()["addressId"]


def test_checkout_delivery_fees_and_inventory(client: TestClient, db_session):
    token, address_id = setup_customer_and_address(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch product with known price and stock
    product = db_session.scalar(select(Product).where(Product.sku == "DAI-MLK-001"))
    assert product is not None
    initial_stock = product.inventory.quantity

    # Add 2 items (price is 2.40 each -> subtotal 4.80 < 20.00 -> delivery fee 1.50)
    client.post(
        "/api/cart/items",
        json={"productId": product.id, "quantity": 2},
        headers=headers,
    )

    # Place Order
    order_resp = client.post(
        "/api/orders",
        json={"addressId": address_id},
        headers=headers,
    )
    assert order_resp.status_code == 201
    order = order_resp.json()

    assert order["status"] == "Pending"
    assert float(order["subtotal"]) == 4.80
    assert float(order["deliveryFee"]) == 1.50
    assert float(order["totalAmount"]) == 6.30
    assert order["canCancel"] is True
    assert order["deliveryAddress"]["recipientName"] == "Order User"
    assert len(order["items"]) == 1

    # Verify inventory was decremented
    db_session.expire_all()
    updated_stock = db_session.scalar(select(Inventory.quantity).where(Inventory.product_id == product.id))
    assert updated_stock == initial_stock - 2

    # Verify StockMovement was recorded
    movement = db_session.scalar(
        select(StockMovement).where(
            StockMovement.reference_id == order["orderId"],
            StockMovement.product_id == product.id,
        )
    )
    assert movement is not None
    assert movement.movement_type == StockMovementType.Sale.value
    assert movement.quantity == -2

    # Verify cart was cleared
    cart_resp = client.get("/api/cart", headers=headers)
    assert cart_resp.json()["itemCount"] == 0


def test_free_delivery_threshold(client: TestClient, db_session):
    token, address_id = setup_customer_and_address(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Jasmine rice 5kg is 6.50. 4 units = 26.00 >= 20.00 -> delivery fee should be 0.00!
    product = db_session.scalar(select(Product).where(Product.sku == "PAN-RIC-001"))
    assert product is not None

    client.post(
        "/api/cart/items",
        json={"productId": product.id, "quantity": 4},
        headers=headers,
    )

    order_resp = client.post(
        "/api/orders",
        json={"addressId": address_id},
        headers=headers,
    )
    assert order_resp.status_code == 201
    order = order_resp.json()

    assert float(order["subtotal"]) == 26.00
    assert float(order["deliveryFee"]) == 0.00
    assert float(order["totalAmount"]) == 26.00

