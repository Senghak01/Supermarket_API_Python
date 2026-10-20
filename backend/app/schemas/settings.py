import datetime
from typing import Optional
from pydantic import Field
from app.schemas.base import CamelCaseModel


class AppSettingResponse(CamelCaseModel):
    key: str
    value: str
    data_type: str
    description: Optional[str] = None
    updated_at: datetime.datetime
    updated_by: Optional[int] = None


class UpdateSettingRequest(CamelCaseModel):
    value: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=255)

