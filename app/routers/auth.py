from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_current_customer
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.customer import CustomerResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse)
@limiter.limit(settings.AUTH_RATE_LIMIT)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.register(body)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.AUTH_RATE_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.login(body)


@router.get("/me", response_model=CustomerResponse)
def get_me(customer: Customer = Depends(get_current_customer)):
    return CustomerResponse(
        customer_id=customer.id,
        username=customer.username,
        email=customer.email,
        first_name=customer.first_name,
        last_name=customer.last_name,
        phone_number=customer.phone_number,
        photo_url=customer.photo_url,
    )

