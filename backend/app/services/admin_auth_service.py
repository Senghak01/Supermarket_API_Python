import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_admin_access_token,
    generate_random_token,
    hash_password,
    hash_token,
    verify_dummy_password,
    verify_password,
)
from app.models.employee import Employee, EmployeeRefreshToken, Role
from app.schemas.admin_auth import (
    EmployeeAuthResponse,
    EmployeeLoginRequest,
    EmployeeProfileResponse,
)


class AdminAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def login(self, request: EmployeeLoginRequest) -> EmployeeAuthResponse:
        email = request.email.strip().lower()

        stmt = (
            select(Employee)
            .options(joinedload(Employee.role))
            .where(Employee.email == email)
        )
        employee = self.db.scalar(stmt)
        if not employee or not employee.password_hash:
            # Timing-safe dummy check
            verify_dummy_password(request.password)
            raise AppError.unauthorized("Invalid employee credentials.")

        if not verify_password(request.password, employee.password_hash):
            raise AppError.unauthorized("Invalid employee credentials.")

        if not employee.is_active:
            raise AppError(status_code=403, message="Your employee account has been deactivated.")

        now = datetime.datetime.now(datetime.timezone.utc)
        role_name = employee.role.name if employee.role else "Staff"

        # Create short-lived (15-min) access token
        access_token = create_admin_access_token(employee.id, employee.email, role_name)
        expires_at = now + datetime.timedelta(minutes=settings.JWT_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)

        # Create long-lived refresh token
        raw_refresh_token = generate_random_token()
        refresh_expires_at = now + datetime.timedelta(days=settings.JWT_ADMIN_REFRESH_TOKEN_EXPIRE_DAYS)

        db_refresh = EmployeeRefreshToken(
            employee_id=employee.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=refresh_expires_at,
            created_at=now,
        )
        self.db.add(db_refresh)
        self.db.commit()

        return EmployeeAuthResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_at=expires_at,
            employee=EmployeeProfileResponse(
                id=employee.id,
                role=role_name,
                username=employee.username,
                email=employee.email,
                first_name=employee.first_name,
                last_name=employee.last_name,
                phone_number=employee.phone_number,
                is_active=employee.is_active,
                created_at=employee.created_at,
            ),
        )

    def refresh(self, raw_refresh_token: str) -> EmployeeAuthResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        token_hash = hash_token(raw_refresh_token.strip())

        stmt = (
            select(EmployeeRefreshToken)
            .options(joinedload(EmployeeRefreshToken.employee).joinedload(Employee.role))
            .where(
                EmployeeRefreshToken.token_hash == token_hash,
                EmployeeRefreshToken.revoked_at.is_(None),
                EmployeeRefreshToken.expires_at > now,
            )
        )
        token_record = self.db.scalar(stmt)
        if not token_record or not token_record.employee or not token_record.employee.is_active:
            raise AppError.unauthorized("Invalid or expired refresh token.")

        employee = token_record.employee
        role_name = employee.role.name if employee.role else "Staff"

        # Issue new access token
        access_token = create_admin_access_token(employee.id, employee.email, role_name)
        expires_at = now + datetime.timedelta(minutes=settings.JWT_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)

        return EmployeeAuthResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,  # Keep same valid refresh token or rotate
            expires_at=expires_at,
            employee=EmployeeProfileResponse(
                id=employee.id,
                role=role_name,
                username=employee.username,
                email=employee.email,
                first_name=employee.first_name,
                last_name=employee.last_name,
                phone_number=employee.phone_number,
                is_active=employee.is_active,
                created_at=employee.created_at,
            ),
        )

    def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_token(raw_refresh_token.strip())
        self.db.execute(
            update(EmployeeRefreshToken)
            .where(EmployeeRefreshToken.token_hash == token_hash)
            .values(revoked_at=datetime.datetime.now(datetime.timezone.utc))
        )
        self.db.commit()

