import datetime
from decimal import Decimal
from typing import List
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.customer import CustomerAddress
from app.schemas.address import AddressResponse, CreateAddressRequest, UpdateAddressRequest

MAX_ADDRESSES = 10


class AddressService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_response(self, a: CustomerAddress) -> AddressResponse:
        return AddressResponse(
            address_id=a.id,
            label=a.label,
            recipient_name=a.recipient_name,
            phone_number=a.phone_number,
            address_line=a.address_line,
            district=a.district,
            city=a.city,
            note=a.note,
            latitude=float(a.latitude) if a.latitude is not None else None,
            longitude=float(a.longitude) if a.longitude is not None else None,
            is_default=a.is_default,
        )

    def _find_owned(self, customer_id: int, address_id: int) -> CustomerAddress:
        stmt = (
            select(CustomerAddress)
            .where(
                CustomerAddress.id == address_id,
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.is_deleted.is_(False)
            )
        )
        address = self.db.scalar(stmt)
        if not address:
            raise AppError.not_found("Address not found.")
        return address

    def get_all(self, customer_id: int) -> List[AddressResponse]:
        stmt = (
            select(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.is_deleted.is_(False)
            )
            .order_by(
                CustomerAddress.is_default.desc(),
                CustomerAddress.created_at.desc()
            )
        )
        addresses = self.db.scalars(stmt).all()
        return [self._to_response(a) for a in addresses]

    def get_by_id(self, customer_id: int, address_id: int) -> AddressResponse:
        return self._to_response(self._find_owned(customer_id, address_id))

    def create(self, customer_id: int, request: CreateAddressRequest) -> AddressResponse:
        stmt = (
            select(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.is_deleted.is_(False)
            )
        )
        existing = self.db.scalars(stmt).all()

        if len(existing) >= MAX_ADDRESSES:
            raise AppError.bad_request(f"You can save up to {MAX_ADDRESSES} addresses.")

        is_default = len(existing) == 0 or request.is_default

        if is_default:
            self._clear_defaults(customer_id)

        address = CustomerAddress(
            customer_id=customer_id,
            label=request.label.strip(),
            recipient_name=request.recipient_name.strip(),
            phone_number=request.phone_number.strip(),
            address_line=request.address_line.strip(),
            district=request.district.strip() if request.district else None,
            city=request.city.strip(),
            note=request.note.strip() if request.note else None,
            latitude=Decimal(str(request.latitude)) if request.latitude is not None else None,
            longitude=Decimal(str(request.longitude)) if request.longitude is not None else None,
            is_default=is_default,
            is_deleted=False,
        )

        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)
        return self._to_response(address)

    def update(self, customer_id: int, address_id: int, request: UpdateAddressRequest) -> AddressResponse:
        address = self._find_owned(customer_id, address_id)

        address.label = request.label.strip()
        address.recipient_name = request.recipient_name.strip()
        address.phone_number = request.phone_number.strip()
        address.address_line = request.address_line.strip()
        address.district = request.district.strip() if request.district else None
        address.city = request.city.strip()
        address.note = request.note.strip() if request.note else None
        address.latitude = Decimal(str(request.latitude)) if request.latitude is not None else None
        address.longitude = Decimal(str(request.longitude)) if request.longitude is not None else None
        address.updated_at = datetime.datetime.now(datetime.timezone.utc)

        if request.is_default and not address.is_default:
            self._clear_defaults(customer_id, except_id=address_id)
            address.is_default = True

        self.db.commit()
        self.db.refresh(address)
        return self._to_response(address)

    def delete(self, customer_id: int, address_id: int) -> None:
        address = self._find_owned(customer_id, address_id)
        was_default = address.is_default

        # Soft delete
        address.is_deleted = True
        address.is_default = False
        address.updated_at = datetime.datetime.now(datetime.timezone.utc)

        if was_default:
            next_addr = self.db.scalar(
                select(CustomerAddress)
                .where(
                    CustomerAddress.customer_id == customer_id,
                    CustomerAddress.id != address_id,
                    CustomerAddress.is_deleted.is_(False)
                )
                .order_by(CustomerAddress.created_at.desc())
            )
            if next_addr:
                next_addr.is_default = True
                next_addr.updated_at = datetime.datetime.now(datetime.timezone.utc)

        self.db.commit()

    def set_default(self, customer_id: int, address_id: int) -> AddressResponse:
        address = self._find_owned(customer_id, address_id)
        self._clear_defaults(customer_id, except_id=address_id)
        address.is_default = True
        address.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()
        self.db.refresh(address)
        return self._to_response(address)

    def _clear_defaults(self, customer_id: int, except_id: int | None = None) -> None:
        stmt = (
            update(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.is_deleted.is_(False),
                CustomerAddress.is_default.is_(True)
            )
        )
        if except_id:
            stmt = stmt.where(CustomerAddress.id != except_id)
        stmt = stmt.values(
            is_default=False,
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.db.execute(stmt)

