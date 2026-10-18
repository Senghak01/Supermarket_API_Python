import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models.catalog import Product


def get_auth_token(client: TestClient) -> str:
    unique_email = f"cart_user_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/auth/register",
        json={"username": "cartuser", "email": unique_email, "password": "Password123!"},
    )
    return resp.json()["token"]


def test_cart_lifecycle_and_calculations(client: TestClient, db_session):
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch an available seeded product
    product = db_session.scalar(select(Product).where(Product.sku == "FRU-BAN-001"))
    assert product is not None

    # 1. Add to cart
    add_resp = client.post(
        "/api/cart/items",
        json={"productId": product.id, "quantity": 2},
        headers=headers,
    )
    assert add_resp.status_code == 200
    cart = add_resp.json()
    assert cart["itemCount"] == 2
    assert float(cart["subtotal"]) == float(product.price * 2)
    assert cart["hasIssues"] is False
    assert len(cart["items"]) == 1

    cart_item_id = cart["items"][0]["cartItemId"]

    # 2. Add more of same product increases quantity
    add_resp2 = client.post(
        "/api/cart/items",
        json={"productId": product.id, "quantity": 3},
        headers=headers,
    )
    assert add_resp2.status_code == 200
    cart2 = add_resp2.json()
    assert cart2["itemCount"] == 5

    # 3. Update quantity
    update_resp = client.put(
        f"/api/cart/items/{cart_item_id}",
        json={"quantity": 4},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["itemCount"] == 4

    # 4. Reject quantity > 99
    err_resp = client.put(
        f"/api/cart/items/{cart_item_id}",
        json={"quantity": 100},
        headers=headers,
    )
    assert err_resp.status_code == 400

    # 5. Reject quantity > available stock
    err_stock = client.post(
        "/api/cart/items",
        json={"productId": product.id, "quantity": 90},
        headers=headers,
    )
    assert err_stock.status_code == 409
    assert "Not enough stock" in err_stock.json()["message"]

    # 6. Remove item
    del_resp = client.delete(f"/api/cart/items/{cart_item_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["itemCount"] == 0

