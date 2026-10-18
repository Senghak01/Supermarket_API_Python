import pytest
from fastapi.testclient import TestClient


def get_token_for(client: TestClient, email: str, pwd: str) -> str:
    resp = client.post("/api/admin/auth/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["accessToken"]


def test_staff_role_permissions(client: TestClient):
    staff_token = get_token_for(client, "staff@supermarket.com", "StaffPass123!")
    headers = {"Authorization": f"Bearer {staff_token}"}

    # 1. Staff CAN view dashboard, products, inventory, orders
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 200
    assert client.get("/api/admin/products", headers=headers).status_code == 200
    assert client.get("/api/admin/inventory", headers=headers).status_code == 200
    assert client.get("/api/admin/orders", headers=headers).status_code == 200

    # 2. Staff is DENIED (403) from mutating catalog
    cat_create = client.post(
        "/api/admin/categories",
        json={"name": "Forbidden Cat"},
        headers=headers,
    )
    assert cat_create.status_code == 403

    # 3. Staff is DENIED (403) from adjusting stock
    stock_adj = client.post(
        "/api/admin/inventory/adjust",
        json={"productId": 1, "delta": 5, "reason": "Test"},
        headers=headers,
    )
    assert stock_adj.status_code == 403

    # 4. Staff is DENIED (403) from purchasing, reports, settings, employees
    assert client.get("/api/admin/purchasing/suppliers", headers=headers).status_code == 403
    assert client.get("/api/admin/reports/sales", headers=headers).status_code == 403
    assert client.get("/api/admin/settings", headers=headers).status_code == 403
    assert client.get("/api/admin/employees", headers=headers).status_code == 403


def test_manager_role_permissions(client: TestClient):
    mgr_token = get_token_for(client, "manager@supermarket.com", "ManagerPass123!")
    headers = {"Authorization": f"Bearer {mgr_token}"}

    # 1. Manager CAN view and adjust stock, purchasing, and sales reports
    assert client.get("/api/admin/purchasing/suppliers", headers=headers).status_code == 200
    assert client.get("/api/admin/reports/sales", headers=headers).status_code == 200

    # 2. Manager is DENIED (403) from employee administration and settings
    assert client.get("/api/admin/employees", headers=headers).status_code == 403
    assert client.get("/api/admin/settings", headers=headers).status_code == 403


def test_admin_full_access(client: TestClient):
    admin_token = get_token_for(client, "admin@supermarket.com", "AdminPass123!")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin CAN access employees, roles, and settings
    assert client.get("/api/admin/employees/roles", headers=headers).status_code == 200
    assert client.get("/api/admin/employees", headers=headers).status_code == 200
    assert client.get("/api/admin/settings", headers=headers).status_code == 200
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 200

