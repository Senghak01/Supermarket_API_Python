import datetime
from typing import Optional
from pydantic import EmailStr, Field
from app.schemas.base import CamelCaseModel


class RoleResponse(CamelCaseModel):
    id: int
    name: str
    description: Optional[str] = None


class CreateEmployeeRequest(CamelCaseModel):
    role_id: int = Field(..., ge=1)
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=72)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=30)


class UpdateEmployeeRequest(CamelCaseModel):
    role_id: Optional[int] = Field(None, ge=1)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None


class ResetPasswordRequest(CamelCaseModel):
    new_password: str = Field(..., min_length=8, max_length=72)


class EmployeeListItem(CamelCaseModel):
    id: int
    role_id: int
    role_name: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

