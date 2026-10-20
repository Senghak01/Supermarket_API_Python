import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.customer import Customer
from app.schemas.customer import CustomerResponse, UpdateProfileRequest


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_profile(self, customer_id: int) -> CustomerResponse:
        customer = self.db.scalar(select(Customer).where(Customer.id == customer_id))
        if not customer:
            raise AppError.not_found("Customer not found.")

        return CustomerResponse(
            customer_id=customer.id,
            username=customer.username,
            email=customer.email,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone_number=customer.phone_number,
            photo_url=customer.photo_url,
        )

    def update_profile(self, customer_id: int, request: UpdateProfileRequest) -> CustomerResponse:
        customer = self.db.scalar(select(Customer).where(Customer.id == customer_id))
        if not customer:
            raise AppError.not_found("Customer not found.")

        customer.username = request.username.strip()
        if request.first_name is not None:
            customer.first_name = request.first_name.strip() or None
        if request.last_name is not None:
            customer.last_name = request.last_name.strip() or None
        if request.phone_number is not None:
            customer.phone_number = request.phone_number.strip() or None
        if request.photo_url is not None:
            customer.photo_url = request.photo_url.strip() or None

        customer.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()
        self.db.refresh(customer)

        return CustomerResponse(
            customer_id=customer.id,
            username=customer.username,
            email=customer.email,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone_number=customer.phone_number,
            photo_url=customer.photo_url,
        )

