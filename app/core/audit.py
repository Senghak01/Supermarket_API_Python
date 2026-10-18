import json
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def record_audit_log(
    db: Session,
    employee_id: Optional[int],
    entity_name: str,
    entity_id: Any,
    action: str,
    diff: Optional[Any] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Helper to record an entry in the audit_logs table."""
    diff_text = None
    if diff is not None:
        if isinstance(diff, (dict, list)):
            diff_text = json.dumps(diff, default=str)
        else:
            diff_text = str(diff)

    log = AuditLog(
        employee_id=employee_id,
        entity_name=entity_name,
        entity_id=str(entity_id),
        action=action,
        diff=diff_text,
        ip_address=ip_address,
    )
    db.add(log)
    return log

