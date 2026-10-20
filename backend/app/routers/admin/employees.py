from typing import List
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.employee import (
    CreateEmployeeRequest,
    EmployeeListItem,
    ResetPasswordRequest,
    RoleResponse,
    UpdateEmployeeRequest,
)
from app.services.admin_employee_service import AdminEmployeeService

router = APIRouter(prefix="/api/admin/employees", tags=["Admin Employees"])


@router.get("/roles", response_model=List[RoleResponse])
def list_roles(
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = AdminEmployeeService(db)
    return service.list_roles()


@router.get("", response_model=List[EmployeeListItem])
def list_employees(
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = AdminEmployeeService(db)
    return service.list_employees()


@router.post("", response_model=EmployeeListItem)
def create_employee(
    request: Request,
    body: CreateEmployeeRequest,
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = AdminEmployeeService(db)
    return service.create_employee(admin.id, body, get_client_ip(request))


@router.put("/{id}", response_model=EmployeeListItem)
def update_employee(
    id: int,
    request: Request,
    body: UpdateEmployeeRequest,
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = AdminEmployeeService(db)
    return service.update_employee(admin.id, id, body, get_client_ip(request))


@router.post("/{id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    id: int,
    request: Request,
    body: ResetPasswordRequest,
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = AdminEmployeeService(db)
    service.reset_password(admin.id, id, body, get_client_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

