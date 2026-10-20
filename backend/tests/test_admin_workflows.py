import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models.catalog import Category, Inventory, Product
from app.models.purchasing import PurchaseOrder, PurchaseStatus, Supplier
from app.models.stock_movement import StockMovement, StockMovementType
from tests.test_admin_roles import get_token_for
from tests.test_checkout import setup_customer_and_address


def test_product_and_category_admin_management(client: TestClient):
    mgr_token = get_token_for(client, "manager@supermarket.com", "ManagerPass123!")
    headers = {"Authorization": f"Bearer {mgr_token}"}

    # 1. Create category
    cat_name = f"Organic Pantry {uuid.uuid4().hex[:6]}"
    cat_resp = client.post(
        "/api/admin/categories",
        json={"name": cat_name, "description": "Organic staples", "isActive": True},
        headers=headers,
    )
    assert cat_resp.status_code == 200
    cat_id = cat_resp.json()["categoryId"]

    # 2. Create product in category with initial stock
    sku = f"ORG-{uuid.uuid4().hex[:6].upper()}"
    prod_resp = client.post(
        "/api/admin/products",
        json={
            "categoryId": cat_id,
            "name": "Organic Chia Seeds 500g",
            "sku": sku,
            "price": 4.50,
            "unit": "bag",
            "initialStock": 25,
            "isActive": True,
        },
        headers=headers,
    )
    assert prod_resp.status_code == 200
    prod_data = prod_resp.json()
    assert prod_data["sku"] == sku
    assert prod_data["stockQuantity"] == 25
    product_id = prod_data["productId"]

    # 3. Update product price and deactivate
    update_resp = client.put(
        f"/api/admin/products/{product_id}",
        json={"price": 4.95, "isActive": False},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert float(update_resp.json()["price"]) == 4.95
    assert update_resp.json()["isActive"] is False


def test_inventory_adjustment_and_movements(client: TestClient, db_session):
    mgr_token = get_token_for(client, "manager@supermarket.com", "ManagerPass123!")
    headers = {"Authorization": f"Bearer {mgr_token}"}

    product = db_session.scalar(select(Product).where(Product.sku == "DAI-EGG-002"))
    assert product is not None
    initial_stock = product.inventory.quantity

    # 1. Adjust stock by +10 (e.g. found stock)
    adj_resp = client.post(
        "/api/admin/inventory/adjust",
        json={"productId": product.id, "delta": 10, "reason": "Physical count adjustment"},
        headers=headers,
    )
    assert adj_resp.status_code == 200
    assert adj_resp.json()["quantity"] == initial_stock + 10

    # 2. Check movement history contains this adjustment with employee name
    hist_resp = client.get(f"/api/admin/inventory/movements?productId={product.id}", headers=headers)
    assert hist_resp.status_code == 200
    items = hist_resp.json()["items"]
    assert len(items) > 0
    latest = items[0]
    assert latest["movementType"] == "Adjustment"
    assert latest["quantity"] == 10
    assert latest["employeeName"] is not None

    # 3. Reject adjustment that would make stock negative
    err_adj = client.post(
        "/api/admin/inventory/adjust",
        json={"productId": product.id, "delta": -(initial_stock + 20), "reason": "Accidental high reduction"},
        headers=headers,
    )
    assert err_adj.status_code == 409
    assert "Cannot decrease stock" in err_adj.json()["message"]


def test_admin_order_progression_and_cod_collection(client: TestClient, db_session):
    staff_token = get_token_for(client, "staff@supermarket.com", "StaffPass123!")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Customer places order
    token, address_id = setup_customer_and_address(client)
    cust_headers = {"Authorization": f"Bearer {token}"}
    product = db_session.scalar(select(Product).where(Product.sku == "BEV-TEA-004"))

    client.post("/api/cart/items", json={"productId": product.id, "quantity": 1}, headers=cust_headers)
    order_id = client.post("/api/orders", json={"addressId": address_id}, headers=cust_headers).json()["orderId"]

    # Choose COD
    client.post(f"/api/orders/{order_id}/payments", json={"method": "CashOnDelivery"}, headers=cust_headers)

    # Order is now Confirmed
    order_detail = client.get(f"/api/admin/orders/{order_id}", headers=staff_headers).json()
    assert order_detail["status"] == "Confirmed"

    # 1. Staff moves status to Preparing
    res_prep = client.post(f"/api/admin/orders/{order_id}/status", json={"status": "Preparing"}, headers=staff_headers)
    assert res_prep.status_code == 200
    assert res_prep.json()["status"] == "Preparing"

    # 2. Staff moves status to ReadyForDelivery
    res_rfd = client.post(f"/api/admin/orders/{order_id}/status", json={"status": "ReadyForDelivery"}, headers=staff_headers)
    assert res_rfd.status_code == 200
    assert res_rfd.json()["status"] == "ReadyForDelivery"

    # 3. Staff moves status to OutForDelivery
    res_ofd = client.post(f"/api/admin/orders/{order_id}/status", json={"status": "OutForDelivery"}, headers=staff_headers)
    assert res_ofd.status_code == 200
    assert res_ofd.json()["status"] == "OutForDelivery"

    # 4. Staff moves status to Delivered
    res_del = client.post(f"/api/admin/orders/{order_id}/status", json={"status": "Delivered"}, headers=staff_headers)
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "Delivered"

    # 5. Staff marks cash on delivery as paid at delivery
    res_paid = client.post(f"/api/admin/orders/{order_id}/mark-cash-paid", headers=staff_headers)
    assert res_paid.status_code == 200
    assert any(p["status"] == "Paid" and p["method"] == "CashOnDelivery" for p in res_paid.json()["payments"])


def test_purchasing_and_receiving_stock(client: TestClient, db_session):
    mgr_token = get_token_for(client, "manager@supermarket.com", "ManagerPass123!")
    headers = {"Authorization": f"Bearer {mgr_token}"}

    supplier = db_session.scalar(select(Supplier).where(Supplier.is_active.is_(True)))
    product = db_session.scalar(select(Product).where(Product.sku == "DAI-BUT-003"))
    initial_stock = product.inventory.quantity

    # 1. Create Purchase Order for 30 units
    po_resp = client.post(
        "/api/admin/purchasing/orders",
        json={
            "supplierId": supplier.id,
            "invoice_number": f"INV-{uuid.uuid4().hex[:6]}",
            "items": [{"productId": product.id, "unitCost": 2.20, "quantity": 30}],
        },
        headers=headers,
    )
    assert po_resp.status_code == 200
    po_id = po_resp.json()["id"]
    assert po_resp.json()["status"] == "Ordered"

    # 2. Receive stock
    rec_resp = client.post(f"/api/admin/purchasing/orders/{po_id}/receive", headers=headers)
    assert rec_resp.status_code == 200
    assert rec_resp.json()["status"] == "Received"

    # 3. Verify product inventory increased by 30
    db_session.expire_all()
    updated_stock = db_session.scalar(select(Inventory.quantity).where(Inventory.product_id == product.id))
    assert updated_stock == initial_stock + 30

    # 4. Verify Purchase stock movement recorded
    movement = db_session.scalar(
        select(StockMovement).where(
            StockMovement.reference_id == po_id,
            StockMovement.movement_type == StockMovementType.Purchase.value,
        )
    )
    assert movement is not None
    assert movement.quantity == 30
    assert movement.employee_id is not None

