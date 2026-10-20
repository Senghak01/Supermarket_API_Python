import datetime
from pydantic import EmailStr, Field
from app.schemas.base import CamelCaseModel
from app.schemas.customer import CustomerResponse


class RegisterRequest(CamelCaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=72)


class LoginRequest(CamelCaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=72)


class AuthResponse(CamelCaseModel):
    token: str
    expires_at: datetime.datetime
    customer: CustomerResponse

