from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.admin_deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.employee import Employee
from app.schemas.audit import AuditLogResponse
from app.schemas.common import PagedResult

router = APIRouter(prefix="/api/admin/audit-logs", tags=["Admin Audit Logs"])


@router.get("", response_model=PagedResult[AuditLogResponse])
def list_audit_logs(
    entity_name: Optional[str] = Query(None, alias="entityName"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=50),
    admin: Employee = Depends(require_roles("Admin")),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)

    query = select(AuditLog).outerjoin(Employee, AuditLog.employee_id == Employee.id).options(joinedload(AuditLog.employee))

    if entity_name:
        query = query.where(AuditLog.entity_name == entity_name)
    if employee_id:
        query = query.where(AuditLog.employee_id == employee_id)

    count_query = select(func.count()).select_from(query.with_only_columns(AuditLog.id).subquery())
    total_count = db.scalar(count_query) or 0

    paged_query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    logs = db.scalars(paged_query).unique().all()

    items = [
        AuditLogResponse(
            id=l.id,
            employee_id=l.employee_id,
            employee_name=(
                f"{l.employee.first_name or ''} {l.employee.last_name or ''}".strip() or l.employee.username
                if l.employee
                else "System / Anonymous"
            ),
            entity_name=l.entity_name,
            entity_id=l.entity_id,
            action=l.action,
            diff=l.diff,
            ip_address=l.ip_address,
            created_at=l.created_at,
        )
        for l in logs
    ]

    return PagedResult[AuditLogResponse](
        items=items,
        page=page,
        page_size=page_size,
        total_count=total_count,
    )

