from typing import Optional
from pydantic import Field
from app.schemas.base import CamelCaseModel


class CreateAddressRequest(CamelCaseModel):
    label: str = Field(default="Home", max_length=30)
    recipient_name: str = Field(..., max_length=100)
    phone_number: str = Field(..., max_length=30)
    address_line: str = Field(..., max_length=255)
    district: Optional[str] = Field(None, max_length=100)
    city: str = Field(..., max_length=100)
    note: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    is_default: bool = False


class UpdateAddressRequest(CreateAddressRequest):
    pass


class AddressResponse(CamelCaseModel):
    address_id: int
    label: str
    recipient_name: str
    phone_number: str
    address_line: str
    district: Optional[str] = None
    city: str
    note: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: bool

