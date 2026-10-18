# Supermarket Backend API (Python / FastAPI)

Mobile-first Supermarket E-Commerce Backend API ported from C# ASP.NET Core to FastAPI + SQLAlchemy 2.0.

---

## 1. Stack & Architecture

- **Framework**: FastAPI + Uvicorn
- **Validation**: Pydantic v2 (configured with `to_camel` alias generator for 100% camelCase compatibility with mobile clients)
- **ORM & Database**: SQLAlchemy 2.0 + PyMySQL (MySQL 8.0)
- **Migrations**: Alembic with full DDL versioning and type preservation
- **Security & Tokens**: bcrypt (timing-safe verification, max 72 bytes validation), PyJWT (HS256 with sub, iss, aud, exp validation)
- **Rate Limiting**: SlowAPI (10/min on auth, 60/min on payment checks, trusting forwarded client IP behind Caddy)
- **Background Tasks**: APScheduler (1-minute unpaid order expiry, 5-second online payment verification worker)
- **Payment Providers**: Cash on Delivery, Sandbox (development), Bakong KHQR (EMVCo dynamic QR code generator with MD5 hash & NBC verification)

---

## 2. API Endpoints

All responses match mobile app expectations and standard error schema: `{ "status": code, "message": "..." }`.

### Authentication & Profile
- `POST /api/auth/register` (rate limited: 10/min)
- `POST /api/auth/login` (timing-safe, rate limited: 10/min)
- `GET /api/auth/me`
- `GET /api/customers/me`
- `PUT /api/customers/me`

### Addresses (Soft-delete & Single Default)
- `GET /api/addresses`
- `GET /api/addresses/{id}`
- `POST /api/addresses`
- `PUT /api/addresses/{id}`
- `PUT /api/addresses/{id}/default`
- `DELETE /api/addresses/{id}`

### Catalog (Public)
- `GET /api/categories`
- `GET /api/categories/{id}`
- `GET /api/products?search&categoryId&minPrice&maxPrice&inStockOnly&sort&page&pageSize`
- `GET /api/products/{id}`

### Shopping Cart
- `GET /api/cart` (includes `items`, `itemCount`, `subtotal`, `hasIssues`)
- `POST /api/cart/items` `{ productId, quantity }` (rejects > 99 or > stock with 409)
- `PUT /api/cart/items/{cartItemId}` `{ quantity }`
- `DELETE /api/cart/items/{cartItemId}`
- `DELETE /api/cart`

### Orders (Atomic Checkout)
- `POST /api/orders` `{ addressId }` (atomic stock deduction, delivery fee calculation, address snapshotting)
- `GET /api/orders?page&pageSize`
- `GET /api/orders/{id}`
- `POST /api/orders/{id}/cancel` (conditional update, stock restoration, return movements)

### Payments
- `POST /api/orders/{orderId}/payments` `{ method: "CashOnDelivery" | "Khqr" | "Card" }`
- `GET /api/orders/{orderId}/payments`
- `POST /api/payments/{id}/check` (rate limited: 60/min)
- `POST /api/payments/{id}/sandbox-confirm` (development only)

### System
- `GET /health` (200 OK when database responds, 503 otherwise)

---

## 3. Concurrency & Race Condition Safety

Stock updates use single atomic conditional SQL statements in strict ascending `product_id` order to avoid deadlocks:
```sql
UPDATE inventories 
SET quantity = quantity - :qty, updated_at = :now 
WHERE product_id = :pid AND quantity >= :qty;
```
If `rowcount == 0`, the transaction rolls back immediately and returns `409 Conflict`.
Orders and cancellations enforce conditional updates (`WHERE status IN ('Pending', 'Confirmed')`), guaranteeing idempotent cancellations and preventing double-refunds or negative stock under high concurrency.

---

## 4. Local Development Setup

1. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate # Linux / macOS
   ```

2. **Install pinned dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   Copy `.env.example` to `.env` and configure your local MySQL credentials and 32+ character JWT secret.

4. **Run migrations & seed development data**:
   ```bash
   alembic upgrade head
   python scripts/seed_dev_data.py
   ```

5. **Start development server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Open `http://localhost:8000/docs` to view Swagger UI.

---

## 5. Running the Tests

The test suite runs against real MySQL to verify real transaction concurrency and race conditions:
```bash
pytest -v
```

---

## 6. Production Deployment (Docker + Caddy + MySQL)

1. Make sure `.env` is configured with production passwords and a rotated 32+ character JWT secret.
2. Launch the isolated multi-container stack:
   ```bash
   docker compose up -d --build
   ```
- **MySQL**: Internal network only; no public ports exposed.
- **FastAPI API**: Internal network only; healthchecked and run as non-root user.
- **Caddy**: Exposes 80/443 with automatic TLS / Let's Encrypt certificates.

