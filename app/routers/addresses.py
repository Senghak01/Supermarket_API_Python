from typing import List
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from app.core.deps import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.address import AddressResponse, CreateAddressRequest, UpdateAddressRequest
from app.services.address_service import AddressService

router = APIRouter(prefix="/api/addresses", tags=["Addresses"])


@router.get("", response_model=List[AddressResponse])
def get_all_addresses(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = AddressService(db)
    return service.get_all(customer.id)


@router.get("/{id}", response_model=AddressResponse)
def get_address_by_id(
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = AddressService(db)
    return service.get_by_id(customer.id, id)


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
def create_address(
    body: CreateAddressRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = AddressService(db)
    return service.create(customer.id, body)


@router.put("/{id}", response_model=AddressResponse)
def update_address(
    id: int,
    body: UpdateAddressRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = AddressService(db)
    return service.update(customer.id, id, body)


@router.put("/{id}/default", response_model=AddressResponse)
def set_default_address(
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = AddressService(db)
    return service.set_default(customer.id, id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    service = AddressService(db)
    service.delete(customer.id, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

