from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_current_customer
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.payment import InitiatePaymentRequest, PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api", tags=["Payments"])


@router.post("/orders/{order_id}/payments", response_model=PaymentResponse)
async def initiate_payment(
    order_id: int,
    body: InitiatePaymentRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = PaymentService(db)
    return await service.initiate_payment(customer.id, order_id, body)


@router.get("/orders/{order_id}/payments", response_model=List[PaymentResponse])
def get_order_payments(
    order_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = PaymentService(db)
    return service.get_for_order(customer.id, order_id)


@router.post("/payments/{id}/check", response_model=PaymentResponse)
@limiter.limit(settings.PAYMENT_CHECK_RATE_LIMIT)
async def check_payment_status(
    request: Request,
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = PaymentService(db)
    return await service.refresh_payment(customer.id, id)


@router.post("/payments/{id}/sandbox-confirm", response_model=PaymentResponse)
async def sandbox_confirm(
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if settings.is_production:
        raise AppError.not_found("Endpoint not available in production.")

    service = PaymentService(db)
    return await service.sandbox_confirm(customer.id, id)

