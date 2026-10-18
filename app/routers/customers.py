from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerResponse, UpdateProfileRequest
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("/me", response_model=CustomerResponse)
def get_my_profile(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CustomerService(db)
    return service.get_profile(customer.id)


@router.put("/me", response_model=CustomerResponse)
def update_my_profile(
    body: UpdateProfileRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = CustomerService(db)
    return service.update_profile(customer.id, body)

