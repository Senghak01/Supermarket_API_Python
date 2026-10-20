import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.employee import Employee, Role
from app.schemas.employee import (
    CreateEmployeeRequest,
    EmployeeListItem,
    ResetPasswordRequest,
    RoleResponse,
    UpdateEmployeeRequest,
)


class AdminEmployeeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_roles(self) -> List[RoleResponse]:
        roles = self.db.scalars(select(Role).order_by(Role.id.asc())).all()
        return [RoleResponse(id=r.id, name=r.name, description=r.description) for r in roles]

    def list_employees(self) -> List[EmployeeListItem]:
        stmt = (
            select(Employee)
            .options(joinedload(Employee.role))
            .order_by(Employee.id.asc())
        )
        employees = self.db.scalars(stmt).all()
        return [
            EmployeeListItem(
                id=e.id,
                role_id=e.role_id,
                role_name=e.role.name if e.role else "",
                username=e.username,
                email=e.email,
                first_name=e.first_name,
                last_name=e.last_name,
                phone_number=e.phone_number,
                is_active=e.is_active,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in employees
        ]

    def create_employee(self, current_admin_id: int, request: CreateEmployeeRequest, ip: Optional[str] = None) -> EmployeeListItem:
        email = request.email.strip().lower()
        existing = self.db.scalar(select(Employee).where(Employee.email == email))
        if existing:
            raise AppError.conflict("An employee account with this email address already exists.")

        role = self.db.scalar(select(Role).where(Role.id == request.role_id))
        if not role:
            raise AppError.bad_request("Invalid role ID.")

        hashed_pw = hash_password(request.password)
        employee = Employee(
            role_id=role.id,
            username=request.username.strip(),
            email=email,
            password_hash=hashed_pw,
            first_name=request.first_name.strip() if request.first_name else None,
            last_name=request.last_name.strip() if request.last_name else None,
            phone_number=request.phone_number.strip() if request.phone_number else None,
            is_active=True,
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)

        record_audit_log(
            self.db,
            current_admin_id,
            "Employee",
            employee.id,
            "CreateEmployee",
            {"email": employee.email, "role": role.name},
            ip,
        )
        self.db.commit()

        return EmployeeListItem(
            id=employee.id,
            role_id=employee.role_id,
            role_name=role.name,
            username=employee.username,
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            phone_number=employee.phone_number,
            is_active=employee.is_active,
            created_at=employee.created_at,
            updated_at=employee.updated_at,
        )

    def update_employee(self, current_admin_id: int, employee_id: int, request: UpdateEmployeeRequest, ip: Optional[str] = None) -> EmployeeListItem:
        employee = self.db.scalar(
            select(Employee)
            .options(joinedload(Employee.role))
            .where(Employee.id == employee_id)
        )
        if not employee:
            raise AppError.not_found("Employee not found.")

        old_role = employee.role.name if employee.role else ""
        old_active = employee.is_active

        if request.role_id is not None:
            role = self.db.scalar(select(Role).where(Role.id == request.role_id))
            if not role:
                raise AppError.bad_request("Invalid role ID.")
            employee.role_id = role.id

        if request.username is not None:
            employee.username = request.username.strip()
        if request.first_name is not None:
            employee.first_name = request.first_name.strip() or None
        if request.last_name is not None:
            employee.last_name = request.last_name.strip() or None
        if request.phone_number is not None:
            employee.phone_number = request.phone_number.strip() or None
        if request.is_active is not None:
            employee.is_active = request.is_active

        employee.updated_at = datetime.datetime.now(datetime.timezone.utc)

        record_audit_log(
            self.db,
            current_admin_id,
            "Employee",
            employee.id,
            "UpdateEmployee",
            {"old_role": old_role, "new_role_id": employee.role_id, "is_active": employee.is_active},
            ip,
        )
        self.db.commit()
        self.db.refresh(employee)

        return EmployeeListItem(
            id=employee.id,
            role_id=employee.role_id,
            role_name=employee.role.name if employee.role else "",
            username=employee.username,
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            phone_number=employee.phone_number,
            is_active=employee.is_active,
            created_at=employee.created_at,
            updated_at=employee.updated_at,
        )

    def reset_password(self, current_admin_id: int, employee_id: int, request: ResetPasswordRequest, ip: Optional[str] = None) -> None:
        employee = self.db.scalar(select(Employee).where(Employee.id == employee_id))
        if not employee:
            raise AppError.not_found("Employee not found.")

        employee.password_hash = hash_password(request.new_password)
        employee.updated_at = datetime.datetime.now(datetime.timezone.utc)

        record_audit_log(
            self.db,
            current_admin_id,
            "Employee",
            employee.id,
            "ResetPassword",
            {"email": employee.email},
            ip,
        )
        self.db.commit()

