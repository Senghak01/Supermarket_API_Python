import concurrent.futures
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.main import create_app
from app.models.catalog import Category, Inventory, Product


def test_concurrent_stock_race_condition_on_real_mysql():
    """
    Spawns 10 concurrent threads attempting to purchase a product with only 5 units in stock.
    Verifies that exactly 5 succeed, 5 fail with 409 Conflict, and stock NEVER goes negative.
    """
    engine = create_engine(settings.DATABASE_URL, pool_size=15, max_overflow=20)
    Session = sessionmaker(bind=engine)

    # 1. Setup a dedicated race test product with exactly 5 units in stock
    with Session() as db:
        category = db.scalar(select(Category).where(Category.is_active.is_(True)))
        assert category is not None

        race_sku = f"RACE-{uuid.uuid4().hex[:6]}"
        product = Product(
            category_id=category.id,
            name="Limited Edition Energy Drink",
            sku=race_sku,
            price=Decimal("2.50"),
            unit="can",
            is_active=True,
        )
        db.add(product)
        db.flush()

        inventory = Inventory(product_id=product.id, quantity=5)
        db.add(inventory)
        db.commit()
        product_id = product.id

    # 2. Setup 10 separate customers with carts containing 1 unit each
    app = create_app()
    customers_data = []
    for i in range(10):
        client = TestClient(app)
        email = f"racer_{i}_{uuid.uuid4().hex[:6]}@test.com"
        ip_header = {"X-Forwarded-For": f"192.168.1.{10+i}"}
        reg = client.post(
            "/api/auth/register",
            json={"username": f"racer{i}", "email": email, "password": "Password123!"},
            headers=ip_header,
        )
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": f"192.168.1.{10+i}"}

        addr = client.post(
            "/api/addresses",
            json={
                "label": "Home",
                "recipientName": f"Racer {i}",
                "phoneNumber": "+85512345678",
                "addressLine": "Norodom Blvd",
                "city": "Phnom Penh",
                "isDefault": True,
            },
            headers=headers,
        )
        address_id = addr.json()["addressId"]

        # Add 1 unit of the limited product to cart
        client.post(
            "/api/cart/items",
            json={"productId": product_id, "quantity": 1},
            headers=headers,
        )
        customers_data.append((client, headers, address_id))

    # 3. Concurrently checkout across 10 threads at the exact same moment
    def do_checkout(client_info):
        cl, hdrs, addr_id = client_info
        return cl.post("/api/orders", json={"addressId": addr_id}, headers=hdrs)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(do_checkout, info) for info in customers_data]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # 4. Analyze results
    successes = [r for r in results if r.status_code == 201]
    conflicts = [r for r in results if r.status_code == 409]

    assert len(successes) == 5, f"Expected exactly 5 successes, got {len(successes)}"
    assert len(conflicts) == 5, f"Expected exactly 5 conflicts, got {len(conflicts)}"

    for c in conflicts:
        assert c.json()["status"] == 409
        assert "out of stock" in c.json()["message"]

    # 5. Check real database inventory
    with Session() as db:
        final_stock = db.scalar(select(Inventory.quantity).where(Inventory.product_id == product_id))
        assert final_stock == 0, f"Expected stock to be exactly 0, got {final_stock}"

    engine.dispose()
