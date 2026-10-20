import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from app.models.catalog import Inventory, Product
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.services.order_service import OrderService
from tests.test_checkout import setup_customer_and_address


def test_cash_on_delivery_flow(client: TestClient, db_session):
    token, address_id = setup_customer_and_address(client)
    headers = {"Authorization": f"Bearer {token}"}

    product = db_session.scalar(select(Product).where(Product.sku == "BAK-BAG-001"))
    client.post("/api/cart/items", json={"productId": product.id, "quantity": 1}, headers=headers)
    order_resp = client.post("/api/orders", json={"addressId": address_id}, headers=headers)
    order_id = order_resp.json()["orderId"]

    # Choose CashOnDelivery
    pay_resp = client.post(
        f"/api/orders/{order_id}/payments",
        json={"method": "CashOnDelivery"},
        headers=headers,
    )
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["method"] == "CashOnDelivery"
    assert pay_data["status"] == "Pending"

    # Order becomes Confirmed immediately for CashOnDelivery
    order_detail = client.get(f"/api/orders/{order_id}", headers=headers).json()
    assert order_detail["status"] == "Confirmed"


def test_sandbox_khqr_and_confirmation(client: TestClient, db_session):
    token, address_id = setup_customer_and_address(client)
    headers = {"Authorization": f"Bearer {token}"}

    product = db_session.scalar(select(Product).where(Product.sku == "BAK-BAG-001"))
    client.post("/api/cart/items", json={"productId": product.id, "quantity": 1}, headers=headers)
    order_resp = client.post("/api/orders", json={"addressId": address_id}, headers=headers)
    order_id = order_resp.json()["orderId"]

    # Initiate KHQR (Sandbox)
    pay_resp = client.post(
        f"/api/orders/{order_id}/payments",
        json={"method": "Khqr"},
        headers=headers,
    )
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["method"] == "Khqr"
    assert pay_data["status"] == "Pending"
    assert "SANDBOX-KHQR" in pay_data["qrData"]
    payment_id = pay_data["paymentId"]

    # Order stays Pending until paid
    order_detail = client.get(f"/api/orders/{order_id}", headers=headers).json()
    assert order_detail["status"] == "Pending"

    # Confirm via sandbox-confirm
    conf_resp = client.post(f"/api/payments/{payment_id}/sandbox-confirm", headers=headers)
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "Paid"

    # Order is now Confirmed
    order_after = client.get(f"/api/orders/{order_id}", headers=headers).json()
    assert order_after["status"] == "Confirmed"
    assert order_after["canCancel"] is False  # Paid orders cannot be cancelled directly


def test_order_expiry_job(client: TestClient, db_session):
    token, address_id = setup_customer_and_address(client)
    headers = {"Authorization": f"Bearer {token}"}

    product = db_session.scalar(select(Product).where(Product.sku == "BAK-BAG-001"))
    client.post("/api/cart/items", json={"productId": product.id, "quantity": 2}, headers=headers)
    order_resp = client.post("/api/orders", json={"addressId": address_id}, headers=headers)
    order_id = order_resp.json()["orderId"]

    # Backdate order creation to 35 minutes ago
    thirty_five_mins_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=35)
    db_session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(created_at=thirty_five_mins_ago)
    )
    db_session.commit()

    # Run expiration service
    service = OrderService(db_session)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)
    cancelled_count = service.expire_unpaid_orders(cutoff)
    assert cancelled_count >= 1

    # Verify order is Cancelled
    order = db_session.scalar(select(Order).where(Order.id == order_id))
    assert order.status == OrderStatus.Cancelled.value

