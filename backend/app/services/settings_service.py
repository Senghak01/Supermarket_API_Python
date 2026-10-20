from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.audit import record_audit_log
from app.core.config import settings as env_settings
from app.core.errors import AppError
from app.models.settings import AppSetting
from app.schemas.settings import AppSettingResponse, UpdateSettingRequest


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all_settings(self) -> List[AppSettingResponse]:
        # Ensure default settings exist in DB
        self._seed_default_settings()
        rows = self.db.scalars(select(AppSetting).order_by(AppSetting.key.asc())).all()
        return [
            AppSettingResponse(
                key=s.key,
                value=s.value,
                data_type=s.data_type,
                description=s.description,
                updated_at=s.updated_at,
                updated_by=s.updated_by,
            )
            for s in rows
        ]

    def update_setting(
        self,
        employee_id: int,
        key: str,
        request: UpdateSettingRequest,
        ip: Optional[str] = None,
    ) -> AppSettingResponse:
        self._seed_default_settings()
        setting = self.db.scalar(select(AppSetting).where(AppSetting.key == key))
        if not setting:
            raise AppError.not_found(f"Setting '{key}' not found.")

        old_value = setting.value
        setting.value = request.value.strip()
        if request.description is not None:
            setting.description = request.description.strip() or None
        setting.updated_by = employee_id

        record_audit_log(
            self.db,
            employee_id=employee_id,
            entity_name="AppSetting",
            entity_id=key,
            action="UpdateSetting",
            diff={"from": old_value, "to": setting.value},
            ip_address=ip,
        )

        self.db.commit()
        self.db.refresh(setting)

        return AppSettingResponse(
            key=setting.key,
            value=setting.value,
            data_type=setting.data_type,
            description=setting.description,
            updated_at=setting.updated_at,
            updated_by=setting.updated_by,
        )

    def _seed_default_settings(self) -> None:
        defaults = [
            ("delivery_flat_fee", str(env_settings.DELIVERY_FLAT_FEE), "decimal", "Standard flat delivery fee in USD"),
            ("delivery_free_threshold", str(env_settings.DELIVERY_FREE_THRESHOLD), "decimal", "Order subtotal threshold for free delivery in USD"),
            ("unpaid_order_expiry_minutes", str(env_settings.UNPAID_ORDER_EXPIRY_MINUTES), "int", "Minutes before an unpaid pending online order expires"),
        ]
        modified = False
        for k, v, dt, desc in defaults:
            existing = self.db.scalar(select(AppSetting).where(AppSetting.key == k))
            if not existing:
                self.db.add(AppSetting(key=k, value=v, data_type=dt, description=desc))
                modified = True
        if modified:
            self.db.commit()

