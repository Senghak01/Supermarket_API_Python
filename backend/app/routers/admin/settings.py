from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.core.rate_limit import get_client_ip
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.settings import AppSettingResponse, UpdateSettingRequest
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/admin/settings", tags=["Admin Settings"])


@router.get("", response_model=List[AppSettingResponse])
def get_all_settings(
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = SettingsService(db)
    return service.get_all_settings()


@router.put("/{key}", response_model=AppSettingResponse)
def update_setting(
    key: str,
    request: Request,
    body: UpdateSettingRequest,
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    service = SettingsService(db)
    return service.update_setting(admin.id, key, body, get_client_ip(request))

