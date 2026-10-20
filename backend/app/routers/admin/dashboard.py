from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.reports import DashboardSummaryResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/admin/dashboard", tags=["Admin Dashboard"])


@router.get("", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    employee: Employee = Depends(require_roles("Admin", "Manager", "Staff")),
    db: Session = Depends(get_db),
):
    service = ReportService(db)
    return service.get_dashboard_summary()

