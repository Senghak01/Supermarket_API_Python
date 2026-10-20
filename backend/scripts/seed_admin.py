import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.employee import Employee, Role
from app.models.purchasing import Supplier
from app.models.settings import AppSetting


def seed_admin_data():
    db = SessionLocal()
    try:
        print("Starting employee & admin bootstrap seeding...")

        # 1. Seed Roles
        roles_data = [
            ("Admin", "Full system administrator with user, role, and configuration rights."),
            ("Manager", "Store manager with access to catalog, inventory, purchasing, orders, and reports."),
            ("Staff", "Store staff handling order picking, delivery, and cash collection."),
        ]
        roles_dict = {}
        for role_name, desc in roles_data:
            role = db.scalar(select(Role).where(Role.name == role_name))
            if not role:
                role = Role(name=role_name, description=desc)
                db.add(role)
                db.flush()
                print(f"Created role: {role_name}")
            roles_dict[role_name] = role

        # 2. Seed Default Admin, Manager, and Staff accounts
        employees_to_seed = [
            ("admin@supermarket.com", "admin", "AdminPass123!", "System", "Administrator", "+85512000001", "Admin"),
            ("manager@supermarket.com", "manager", "ManagerPass123!", "Sopheap", "Chan", "+85512000002", "Manager"),
            ("staff@supermarket.com", "staff", "StaffPass123!", "Dara", "Vann", "+85512000003", "Staff"),
        ]

        for email, username, pwd, fname, lname, phone, role_key in employees_to_seed:
            emp = db.scalar(select(Employee).where(Employee.email == email))
            if not emp:
                emp = Employee(
                    role_id=roles_dict[role_key].id,
                    username=username,
                    email=email,
                    password_hash=hash_password(pwd),
                    first_name=fname,
                    last_name=lname,
                    phone_number=phone,
                    is_active=True,
                )
                db.add(emp)
                print(f"Created employee: {email} (Role: {role_key}) / Password: {pwd}")

        # 3. Seed Default Suppliers
        suppliers_data = [
            ("CP Cambodia Trading", "Mr. Somchai", "orders@cpcambodia.com", "+85523999111", "Veng Sreng Blvd, Phnom Penh"),
            ("Kirirom Food Production", "Mrs. Bopha", "sales@kiriromfood.com", "+85523888222", "Kirirom National Park Rd, Kampong Speu"),
            ("Angkor Dairy Co.", "Mr. Chenda", "supply@angkordairy.com", "+85523777333", "National Road 4, Phnom Penh"),
        ]

        for s_name, c_name, s_email, s_phone, s_addr in suppliers_data:
            supplier = db.scalar(select(Supplier).where(Supplier.name == s_name))
            if not supplier:
                supplier = Supplier(
                    name=s_name,
                    contact_name=c_name,
                    email=s_email,
                    phone=s_phone,
                    address=s_addr,
                    is_active=True,
                )
                db.add(supplier)
                print(f"Created supplier: {s_name}")

        # 4. Seed Settings
        default_settings = [
            ("delivery_flat_fee", "1.50", "decimal", "Standard flat delivery fee in USD"),
            ("delivery_free_threshold", "20.00", "decimal", "Order subtotal threshold for free delivery in USD"),
            ("unpaid_order_expiry_minutes", "30", "int", "Minutes before an unpaid pending online order expires"),
        ]

        for k, v, dt, desc in default_settings:
            setting = db.scalar(select(AppSetting).where(AppSetting.key == k))
            if not setting:
                setting = AppSetting(key=k, value=v, data_type=dt, description=desc)
                db.add(setting)
                print(f"Created setting: {k} = {v}")

        db.commit()
        print("Employee and admin seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding admin data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin_data()

