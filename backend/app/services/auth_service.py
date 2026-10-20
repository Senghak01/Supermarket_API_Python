import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.models.customer import Customer
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.customer import CustomerResponse


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, request: RegisterRequest) -> AuthResponse:
        email = request.email.strip().lower()
        username = request.username.strip()

        # Check existing customer
        existing = self.db.scalar(select(Customer).where(Customer.email == email))
        if existing:
            raise AppError.conflict("An account with this email address already exists.")

        hashed_password = hash_password(request.password)

        customer = Customer(
            username=username,
            email=email,
            password_hash=hashed_password,
            is_active=True,
        )
        self.db.add(customer)

        try:
            self.db.commit()
            self.db.refresh(customer)
        except IntegrityError:
            self.db.rollback()
            raise AppError.conflict("An account with this email address already exists.")

        token = create_access_token(customer.id, customer.email)
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

        return AuthResponse(
            token=token,
            expires_at=expires_at,
            customer=CustomerResponse(
                customer_id=customer.id,
                username=customer.username,
                email=customer.email,
                first_name=customer.first_name,
                last_name=customer.last_name,
                phone_number=customer.phone_number,
                photo_url=customer.photo_url,
            ),
        )

    def login(self, request: LoginRequest) -> AuthResponse:
        email = request.email.strip().lower()

        customer = self.db.scalar(select(Customer).where(Customer.email == email))
        if not customer or not customer.password_hash:
            # Timing-safe dummy check
            verify_dummy_password(request.password)
            raise AppError.unauthorized("Invalid email or password.")

        if not verify_password(request.password, customer.password_hash):
            raise AppError.unauthorized("Invalid email or password.")

        if not customer.is_active:
            raise AppError(status_code=403, message="Your account has been deactivated.")

        token = create_access_token(customer.id, customer.email)
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

        return AuthResponse(
            token=token,
            expires_at=expires_at,
            customer=CustomerResponse(
                customer_id=customer.id,
                username=customer.username,
                email=customer.email,
                first_name=customer.first_name,
                last_name=customer.last_name,
                phone_number=customer.phone_number,
                photo_url=customer.photo_url,
            ),
        )

