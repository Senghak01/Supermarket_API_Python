import datetime
from typing import Optional
from app.schemas.base import CamelCaseModel


class AuditLogResponse(CamelCaseModel):
    id: int
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    entity_name: str
    entity_id: str
    action: str
    diff: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime.datetime

