import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app.core.admin_deps import require_roles
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.reports import (
    InventoryValuationResponse,
    SalesReportResponse,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/admin/reports", tags=["Admin Reports"])


@router.get("/sales", response_model=SalesReportResponse)
def get_sales_report(
    date_from: Optional[datetime.date] = Query(None, alias="dateFrom"),
    date_to: Optional[datetime.date] = Query(None, alias="dateTo"),
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = ReportService(db)
    return service.get_sales_report(date_from=date_from, date_to=date_to)


@router.get("/inventory-valuation", response_model=InventoryValuationResponse)
def get_inventory_valuation(
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = ReportService(db)
    return service.get_inventory_valuation()


@router.get("/sales/export-csv")
def export_sales_csv(
    date_from: Optional[datetime.date] = Query(None, alias="dateFrom"),
    date_to: Optional[datetime.date] = Query(None, alias="dateTo"),
    employee: Employee = Depends(require_roles("Admin", "Manager")),
    db: Session = Depends(get_db),
):
    service = ReportService(db)
    csv_data = service.export_sales_csv(date_from=date_from, date_to=date_to)
    filename = f"sales_report_{datetime.date.today()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

