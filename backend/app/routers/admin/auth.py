from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from app.core.admin_deps import get_current_employee
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.admin_auth import (
    EmployeeAuthResponse,
    EmployeeLoginRequest,
    EmployeeProfileResponse,
    EmployeeRefreshTokenRequest,
)
from app.services.admin_auth_service import AdminAuthService

router = APIRouter(prefix="/api/admin/auth", tags=["Admin Auth"])


@router.post("/login", response_model=EmployeeAuthResponse)
@limiter.limit(settings.ADMIN_AUTH_RATE_LIMIT)
def admin_login(request: Request, body: EmployeeLoginRequest, db: Session = Depends(get_db)):
    service = AdminAuthService(db)
    return service.login(body)


@router.post("/refresh", response_model=EmployeeAuthResponse)
def admin_refresh_token(body: EmployeeRefreshTokenRequest, db: Session = Depends(get_db)):
    service = AdminAuthService(db)
    return service.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_logout(body: EmployeeRefreshTokenRequest, db: Session = Depends(get_db)):
    service = AdminAuthService(db)
    service.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=EmployeeProfileResponse)
def admin_me(employee: Employee = Depends(get_current_employee)):
    return EmployeeProfileResponse(
        id=employee.id,
        role=employee.role.name if employee.role else "Staff",
        username=employee.username,
        email=employee.email,
        first_name=employee.first_name,
        last_name=employee.last_name,
        phone_number=employee.phone_number,
        is_active=employee.is_active,
        created_at=employee.created_at,
    )

