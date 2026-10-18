import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware

from app.background.scheduler import start_scheduler, stop_scheduler
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.middleware import SecurityHeadersAndBodyLimitMiddleware
from app.core.rate_limit import limiter
from app.routers import (
    addresses,
    auth,
    cart,
    categories,
    customers,
    health,
    orders,
    payments,
    products,
)
from app.routers.admin import (
    audit as admin_audit,
    auth as admin_auth,
    categories as admin_categories,
    customers as admin_customers,
    dashboard as admin_dashboard,
    employees as admin_employees,
    inventory as admin_inventory,
    orders as admin_orders,
    products as admin_products,
    purchasing as admin_purchasing,
    reports as admin_reports,
    settings as admin_settings,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.is_production else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("supermarket.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background workers (order expiry & payment verifier)
    if settings.ENVIRONMENT != "test":
        logger.info(f"Starting Supermarket API in {settings.ENVIRONMENT} mode...")
        start_scheduler()
    yield
    # Shutdown: Stop background workers
    if settings.ENVIRONMENT != "test":
        logger.info("Stopping Supermarket API...")
        stop_scheduler()


def create_app() -> FastAPI:
    # Disable OpenAPI documentation in production for security
    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"
    openapi_url = None if settings.is_production else "/openapi.json"

    app = FastAPI(
        title="Supermarket API & Admin Management",
        version="1.1.0",
        description="Mobile & Web Supermarket Management Backend API",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # CORS Middleware: allow admin web frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach SlowAPI rate limiter
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # Security headers and max 1MB body limit middleware
    app.add_middleware(SecurityHeadersAndBodyLimitMiddleware)

    # Global standardized error responses: { "status": code, "message": "..." }
    register_error_handlers(app)

    # Static uploads mount for product images
    uploads_path = Path("uploads")
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

    # Public & Mobile Client Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(customers.router)
    app.include_router(addresses.router)
    app.include_router(categories.router)
    app.include_router(products.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.include_router(payments.router)

    # Employee & Admin Management Routers
    app.include_router(admin_auth.router)
    app.include_router(admin_dashboard.router)
    app.include_router(admin_categories.router)
    app.include_router(admin_products.router)
    app.include_router(admin_inventory.router)
    app.include_router(admin_orders.router)
    app.include_router(admin_customers.router)
    app.include_router(admin_purchasing.router)
    app.include_router(admin_employees.router)
    app.include_router(admin_reports.router)
    app.include_router(admin_settings.router)
    app.include_router(admin_audit.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
