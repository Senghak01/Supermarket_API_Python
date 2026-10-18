import pytest
from fastapi.testclient import TestClient


def test_admin_login_success(client: TestClient):
    resp = client.post(
        "/api/admin/auth/login",
        json={"email": "admin@supermarket.com", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "accessToken" in data
    assert "refreshToken" in data
    assert "expiresAt" in data
    assert data["employee"]["email"] == "admin@supermarket.com"
    assert data["employee"]["role"] == "Admin"

    token = data["accessToken"]

    # Verify /me endpoint
    me_resp = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@supermarket.com"


def test_customer_token_cannot_access_admin_endpoints(client: TestClient):
    # 1. Login as customer
    cust_resp = client.post(
        "/api/auth/login",
        json={"email": "customer@supermarket.com", "password": "Password123!"},
    )
    assert cust_resp.status_code == 200
    customer_token = cust_resp.json()["token"]

    # 2. Attempt to use customer token on admin dashboard
    admin_resp = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    # Token audience mismatch -> 401 Unauthorized
    assert admin_resp.status_code == 401
    assert "Invalid administrator credentials" in admin_resp.json()["message"]


def test_admin_refresh_token_lifecycle(client: TestClient):
    # Login
    login_resp = client.post(
        "/api/admin/auth/login",
        json={"email": "manager@supermarket.com", "password": "ManagerPass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refreshToken"]

    # Refresh
    ref_resp = client.post(
        "/api/admin/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert ref_resp.status_code == 200
    new_token = ref_resp.json()["accessToken"]
    assert new_token is not None

    # Verify new token works
    me_resp = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "Manager"

    # Logout
    logout_resp = client.post(
        "/api/admin/auth/logout",
        json={"refreshToken": refresh_token},
    )
    assert logout_resp.status_code == 204

    # Using revoked refresh token must now fail
    fail_ref = client.post(
        "/api/admin/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert fail_ref.status_code == 401

