import datetime
from typing import Optional
from pydantic import EmailStr, Field
from app.schemas.base import CamelCaseModel


class EmployeeLoginRequest(CamelCaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=72)


class EmployeeRefreshTokenRequest(CamelCaseModel):
    refresh_token: str = Field(..., min_length=1)


class EmployeeProfileResponse(CamelCaseModel):
    id: int
    role: str
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime


class EmployeeAuthResponse(CamelCaseModel):
    access_token: str
    refresh_token: str
    expires_at: datetime.datetime
    employee: EmployeeProfileResponse

