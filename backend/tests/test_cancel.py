import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models.catalog import Inventory, Product
from app.models.stock_movement import StockMovement, StockMovementType
from tests.test_checkout import setup_customer_and_address


def test_cancel_order_restores_stock(client: TestClient, db_session):
    token, address_id = setup_customer_and_address(client)
    headers = {"Authorization": f"Bearer {token}"}

    product = db_session.scalar(select(Product).where(Product.sku == "BEV-WAT-001"))
    assert product is not None
    initial_stock = product.inventory.quantity

    # Add 5 items to cart and checkout
    client.post("/api/cart/items", json={"productId": product.id, "quantity": 5}, headers=headers)
    order_resp = client.post("/api/orders", json={"addressId": address_id}, headers=headers)
    order_id = order_resp.json()["orderId"]

    # Stock should be decreased by 5
    db_session.expire_all()
    decreased_stock = db_session.scalar(select(Inventory.quantity).where(Inventory.product_id == product.id))
    assert decreased_stock == initial_stock - 5

    # Cancel order
    cancel_resp = client.post(f"/api/orders/{order_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    cancelled_order = cancel_resp.json()
    assert cancelled_order["status"] == "Cancelled"
    assert cancelled_order["canCancel"] is False

    # Stock must be restored to initial
    db_session.expire_all()
    restored_stock = db_session.scalar(select(Inventory.quantity).where(Inventory.product_id == product.id))
    assert restored_stock == initial_stock

    # Return StockMovement should exist
    ret_movement = db_session.scalar(
        select(StockMovement).where(
            StockMovement.reference_id == order_id,
            StockMovement.movement_type == StockMovementType.Return.value,
        )
    )
    assert ret_movement is not None
    assert ret_movement.quantity == 5

    # Second cancel must fail with 409 conflict
    cancel2 = client.post(f"/api/orders/{order_id}/cancel", headers=headers)
    assert cancel2.status_code == 409
    assert "no longer be cancelled" in cancel2.json()["message"]

