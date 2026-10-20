import csv
import datetime
import io
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from app.models.catalog import Category, Inventory, Product
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.reports import (
    DashboardSummaryResponse,
    InventoryValuationResponse,
    SalesReportItem,
    SalesReportResponse,
)

LOW_STOCK_THRESHOLD = 10


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard_summary(self) -> DashboardSummaryResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Sales today & Orders today
        today_stats = self.db.execute(
            select(
                func.count(Order.id).label("cnt"),
                func.coalesce(func.sum(Order.total_amount), Decimal("0.00")).label("sales"),
            )
            .where(
                Order.created_at >= today_start,
                Order.status != OrderStatus.Cancelled.value,
            )
        ).first()

        orders_today_count = today_stats.cnt if today_stats else 0
        sales_today = today_stats.sales if today_stats else Decimal("0.00")

        # Low stock count
        low_stock_count = self.db.scalar(
            select(func.count(Inventory.id)).where(Inventory.quantity <= LOW_STOCK_THRESHOLD)
        ) or 0

        # Pending orders waiting too long (> 15 minutes)
        fifteen_mins_ago = now - datetime.timedelta(minutes=15)
        pending_orders_waiting_count = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.status == OrderStatus.Pending.value,
                Order.created_at <= fifteen_mins_ago,
            )
        ) or 0

        # Orders by status today
        status_counts_rows = self.db.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.created_at >= today_start)
            .group_by(Order.status)
        ).all()

        orders_by_status = {s.value: 0 for s in OrderStatus}
        for st, count in status_counts_rows:
            orders_by_status[st] = count

        return DashboardSummaryResponse(
            sales_today=sales_today,
            orders_today_count=orders_today_count,
            low_stock_count=low_stock_count,
            pending_orders_waiting_count=pending_orders_waiting_count,
            orders_by_status=orders_by_status,
        )

    def get_sales_report(
        self,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
    ) -> SalesReportResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        if not date_from:
            date_from = (now - datetime.timedelta(days=7)).date()
        if not date_to:
            date_to = now.date()

        dt_from = datetime.datetime.combine(date_from, datetime.time.min).replace(tzinfo=datetime.timezone.utc)
        dt_to = datetime.datetime.combine(date_to, datetime.time.max).replace(tzinfo=datetime.timezone.utc)

        # Group by date
        stmt = (
            select(
                func.date(Order.created_at).label("day"),
                func.count(Order.id).label("orders_count"),
                func.coalesce(func.sum(Order.total_amount), Decimal("0.00")).label("total_sales"),
                func.coalesce(func.sum(Order.discount), Decimal("0.00")).label("total_discount"),
                func.coalesce(func.sum(Order.delivery_fee), Decimal("0.00")).label("total_delivery_fees"),
            )
            .where(
                Order.created_at >= dt_from,
                Order.created_at <= dt_to,
                Order.status != OrderStatus.Cancelled.value,
            )
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at).asc())
        )
        rows = self.db.execute(stmt).all()

        items = []
        grand_total = Decimal("0.00")
        total_orders = 0
        total_items_sold = 0

        for r in rows:
            day_str = str(r.day)
            # Count items sold on this day
            items_sold_count = self.db.scalar(
                select(func.coalesce(func.sum(OrderItem.quantity), 0))
                .join(Order, OrderItem.order_id == Order.id)
                .where(
                    func.date(Order.created_at) == r.day,
                    Order.status != OrderStatus.Cancelled.value,
                )
            ) or 0

            items.append(
                SalesReportItem(
                    period=day_str,
                    orders_count=r.orders_count,
                    items_sold=items_sold_count,
                    total_sales=r.total_sales,
                    total_discount=r.total_discount,
                    total_delivery_fees=r.total_delivery_fees,
                )
            )
            grand_total += r.total_sales
            total_orders += r.orders_count
            total_items_sold += items_sold_count

        return SalesReportResponse(
            items=items,
            grand_total_sales=grand_total,
            grand_total_orders=total_orders,
            grand_total_items=total_items_sold,
        )

    def get_inventory_valuation(self) -> InventoryValuationResponse:
        stmt = select(
            func.count(Product.id).label("prod_count"),
            func.coalesce(func.sum(Inventory.quantity), 0).label("units_count"),
            func.coalesce(func.sum(Product.price * Inventory.quantity), Decimal("0.00")).label("retail_val"),
            func.count(case((Inventory.quantity <= LOW_STOCK_THRESHOLD, 1))).label("low_stock_count"),
            func.count(case((Inventory.quantity == 0, 1))).label("out_stock_count"),
        ).join(Inventory, Product.id == Inventory.product_id)

        stats = self.db.execute(stmt).first()
        if not stats:
            return InventoryValuationResponse(
                total_products=0,
                total_stock_units=0,
                total_retail_value=Decimal("0.00"),
                low_stock_products_count=0,
                out_of_stock_products_count=0,
            )

        return InventoryValuationResponse(
            total_products=stats.prod_count,
            total_stock_units=stats.units_count,
            total_retail_value=stats.retail_val,
            low_stock_products_count=stats.low_stock_count,
            out_of_stock_products_count=stats.out_stock_count,
        )

    def export_sales_csv(
        self,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
    ) -> str:
        report = self.get_sales_report(date_from, date_to)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Period (Date)", "Orders Count", "Items Sold", "Total Delivery Fees ($)", "Discounts ($)", "Net Sales ($)"])

        for row in report.items:
            writer.writerow([
                row.period,
                row.orders_count,
                row.items_sold,
                f"{row.total_delivery_fees:.2f}",
                f"{row.total_discount:.2f}",
                f"{row.total_sales:.2f}",
            ])

        writer.writerow([])
        writer.writerow(["TOTALS", report.grand_total_orders, report.grand_total_items, "", "", f"{report.grand_total_sales:.2f}"])

        return output.getvalue()

