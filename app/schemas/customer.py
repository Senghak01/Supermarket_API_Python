from typing import Optional
from pydantic import EmailStr, Field
from app.schemas.base import CamelCaseModel


class CustomerResponse(CamelCaseModel):
    customer_id: int
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    photo_url: Optional[str] = None


class UpdateProfileRequest(CamelCaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=30)
    photo_url: Optional[str] = Field(None, max_length=500)

