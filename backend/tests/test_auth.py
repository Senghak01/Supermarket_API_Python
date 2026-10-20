import uuid
import pytest
from fastapi.testclient import TestClient


def test_register_and_login_success(client: TestClient):
    unique_email = f"user_{uuid.uuid4().hex[:8]}@test.com"

    # Register
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": unique_email,
            "password": "Password123!",
        },
    )
    assert reg_resp.status_code == 200
    data = reg_resp.json()
    assert "token" in data
    assert "expiresAt" in data
    assert data["customer"]["email"] == unique_email
    assert data["customer"]["username"] == "testuser"

    token = data["token"]

    # Login
    login_resp = client.post(
        "/api/auth/login",
        json={
            "email": unique_email,
            "password": "Password123!",
        },
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "token" in login_data
    assert login_data["customer"]["email"] == unique_email

    # Me
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == unique_email


def test_duplicate_registration_returns_409(client: TestClient):
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@test.com"

    # First register
    res1 = client.post(
        "/api/auth/register",
        json={
            "username": "user1",
            "email": unique_email,
            "password": "Password123!",
        },
    )
    assert res1.status_code == 200

    # Second register with same email
    res2 = client.post(
        "/api/auth/register",
        json={
            "username": "user2",
            "email": unique_email,
            "password": "Password123!",
        },
    )
    assert res2.status_code == 409
    err = res2.json()
    assert err["status"] == 409
    assert "already exists" in err["message"]


def test_login_timing_safe_error_messages(client: TestClient):
    # Unknown email
    res1 = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent_email_12345@test.com",
            "password": "Password123!",
        },
    )
    assert res1.status_code == 401
    assert res1.json() == {"status": 401, "message": "Invalid email or password."}

    # Known email with wrong password
    res2 = client.post(
        "/api/auth/login",
        json={
            "email": "customer@supermarket.com",
            "password": "WrongPassword999!",
        },
    )
    assert res2.status_code == 401
    assert res2.json() == {"status": 401, "message": "Invalid email or password."}

