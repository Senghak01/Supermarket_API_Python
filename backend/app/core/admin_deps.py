from typing import Callable
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.errors import AppError
from app.core.security import decode_admin_token
from app.db.session import get_db
from app.models.employee import Employee

admin_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_employee(
    credentials: HTTPAuthorizationCredentials = Depends(admin_bearer_scheme),
    db: Session = Depends(get_db),
) -> Employee:
    """Dependency that reads the Admin JWT Bearer token, validates it, and loads the active employee with role."""
    if not credentials or not credentials.credentials:
        raise AppError(status_code=401, message="Administrator authentication required. Please provide a Bearer token.")

    token = credentials.credentials
    payload = decode_admin_token(token)

    emp_id_str = payload.get("sub")
    if not emp_id_str:
        raise AppError.unauthorized("Invalid admin token payload.")

    try:
        employee_id = int(emp_id_str)
    except ValueError:
        raise AppError.unauthorized("Invalid employee identifier.")

    employee = db.scalar(
        select(Employee)
        .options(joinedload(Employee.role))
        .where(Employee.id == employee_id)
    )
    if not employee:
        raise AppError.unauthorized("Employee account not found.")

    if not employee.is_active:
        raise AppError(status_code=403, message="Your employee account has been deactivated.")

    return employee


def require_roles(*allowed_roles: str) -> Callable:
    """FastAPI dependency factory enforcing server-side role-based authorization."""
    def role_checker(employee: Employee = Depends(get_current_employee)) -> Employee:
        if not employee.role or employee.role.name not in allowed_roles:
            raise AppError(
                status_code=403,
                message=f"Access denied. Requires one of the following roles: {', '.join(allowed_roles)}."
            )
        return employee

    return role_checker

