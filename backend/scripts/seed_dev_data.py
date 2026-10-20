import sys
from decimal import Decimal
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.catalog import Category, Inventory, Product
from app.models.customer import Customer, CustomerAddress


def seed_data():
    db = SessionLocal()
    try:
        print("Starting development data seeding...")

        # 1. Seed Customer
        existing_customer = db.scalar(select(Customer).where(Customer.email == "customer@supermarket.com"))
        if not existing_customer:
            customer = Customer(
                username="channita",
                email="customer@supermarket.com",
                password_hash=hash_password("Password123!"),
                first_name="Channita",
                last_name="Sok",
                phone_number="+85512345678",
                is_active=True,
            )
            db.add(customer)
            db.flush()

            address = CustomerAddress(
                customer_id=customer.id,
                label="Home",
                recipient_name="Channita Sok",
                phone_number="+85512345678",
                address_line="#123, St 63, Boeung Keng Kang 1",
                district="Chamkarmon",
                city="Phnom Penh",
                latitude=Decimal("11.5529"),
                longitude=Decimal("104.9282"),
                is_default=True,
            )
            db.add(address)
            print("Created default test customer: customer@supermarket.com / Password123!")

        # 2. Seed Categories & Products
        categories_data = [
            {
                "name": "Fresh Fruits & Vegetables",
                "description": "Organic fresh local fruits and vegetables",
                "image_url": "https://images.unsplash.com/photo-1610832958506-aa56368176cf",
                "products": [
                    {"name": "Organic Cavendish Bananas", "sku": "FRU-BAN-001", "price": Decimal("1.20"), "unit": "kg", "stock": 50},
                    {"name": "Fresh Red Apples", "sku": "FRU-APP-002", "price": Decimal("2.80"), "unit": "kg", "stock": 40},
                    {"name": "Crispy Green Lettuce", "sku": "VEG-LET-003", "price": Decimal("0.90"), "unit": "pack", "stock": 30},
                    {"name": "Hydroponic Cherry Tomatoes", "sku": "VEG-TOM-004", "price": Decimal("1.50"), "unit": "box", "stock": 25},
                ],
            },
            {
                "name": "Dairy, Eggs & Chilled",
                "description": "Milk, butter, cheeses and farm eggs",
                "image_url": "https://images.unsplash.com/photo-1550583724-b2692b85b150",
                "products": [
                    {"name": "Fresh Whole Milk 1L", "sku": "DAI-MLK-001", "price": Decimal("2.40"), "unit": "bottle", "stock": 60},
                    {"name": "Farm Fresh Eggs 10pcs", "sku": "DAI-EGG-002", "price": Decimal("2.10"), "unit": "pack", "stock": 45},
                    {"name": "Salted Butter 200g", "sku": "DAI-BUT-003", "price": Decimal("3.20"), "unit": "block", "stock": 20},
                    {"name": "Greek Yogurt Plain 500g", "sku": "DAI-YOG-004", "price": Decimal("3.80"), "unit": "tub", "stock": 15},
                ],
            },
            {
                "name": "Beverages & Drinks",
                "description": "Mineral water, juices, soda, coffee and tea",
                "image_url": "https://images.unsplash.com/photo-1527661591475-527312dd65f5",
                "products": [
                    {"name": "Natural Mineral Water 1.5L", "sku": "BEV-WAT-001", "price": Decimal("0.75"), "unit": "bottle", "stock": 100},
                    {"name": "100% Orange Juice 1L", "sku": "BEV-JUC-002", "price": Decimal("3.10"), "unit": "bottle", "stock": 35},
                    {"name": "Arabica Whole Bean Coffee 250g", "sku": "BEV-COF-003", "price": Decimal("5.50"), "unit": "bag", "stock": 25},
                    {"name": "Green Tea Bags 25s", "sku": "BEV-TEA-004", "price": Decimal("2.30"), "unit": "box", "stock": 40},
                ],
            },
            {
                "name": "Bakery & Breakfast",
                "description": "Freshly baked artisan breads, croissants and jams",
                "image_url": "https://images.unsplash.com/photo-1509440159596-0249088772ff",
                "products": [
                    {"name": "French Baguette", "sku": "BAK-BAG-001", "price": Decimal("1.10"), "unit": "loaf", "stock": 20},
                    {"name": "Butter Croissant 2pcs", "sku": "BAK-CRO-002", "price": Decimal("2.20"), "unit": "pack", "stock": 18},
                    {"name": "Whole Wheat Bread 400g", "sku": "BAK-WHT-003", "price": Decimal("1.80"), "unit": "loaf", "stock": 25},
                ],
            },
            {
                "name": "Pantry & Staples",
                "description": "Rice, noodles, cooking oils, sauces and seasonings",
                "image_url": "https://images.unsplash.com/photo-1584473457406-6240486418e9",
                "products": [
                    {"name": "Cambodian Jasmine Rice 5kg", "sku": "PAN-RIC-001", "price": Decimal("6.50"), "unit": "bag", "stock": 50},
                    {"name": "Pure Olive Oil 500ml", "sku": "PAN-OIL-002", "price": Decimal("7.20"), "unit": "bottle", "stock": 20},
                    {"name": "Premium Soy Sauce 500ml", "sku": "PAN-SOY-003", "price": Decimal("1.60"), "unit": "bottle", "stock": 40},
                ],
            },
        ]

        for cat_data in categories_data:
            cat_name = cat_data["name"]
            category = db.scalar(select(Category).where(Category.name == cat_name))
            if not category:
                category = Category(
                    name=cat_name,
                    description=cat_data["description"],
                    image_url=cat_data["image_url"],
                    is_active=True,
                )
                db.add(category)
                db.flush()

            for prod_data in cat_data["products"]:
                existing_prod = db.scalar(select(Product).where(Product.sku == prod_data["sku"]))
                if not existing_prod:
                    product = Product(
                        category_id=category.id,
                        name=prod_data["name"],
                        sku=prod_data["sku"],
                        price=prod_data["price"],
                        unit=prod_data["unit"],
                        description=f"Fresh quality {prod_data['name']} for your daily grocery needs.",
                        image_url=cat_data["image_url"],
                        is_active=True,
                    )
                    db.add(product)
                    db.flush()

                    inventory = Inventory(
                        product_id=product.id,
                        quantity=prod_data["stock"],
                    )
                    db.add(inventory)

        db.commit()
        print("Data seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()

