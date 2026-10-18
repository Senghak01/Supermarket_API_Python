from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.customer import Customer

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Customer:
    """Dependency that reads the JWT Bearer token, validates it, and loads the active customer."""
    if not credentials or not credentials.credentials:
        raise AppError(status_code=401, message="Authentication required. Please provide a Bearer token.")

    token = credentials.credentials
    payload = decode_access_token(token)

    customer_id_str = payload.get("sub")
    if not customer_id_str:
        raise AppError.unauthorized("Invalid token payload.")

    try:
        customer_id = int(customer_id_str)
    except ValueError:
        raise AppError.unauthorized("Invalid customer identifier.")

    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise AppError.unauthorized("Customer account not found.")

    if not customer.is_active:
        raise AppError(status_code=403, message="Your account has been deactivated.")

    return customer

