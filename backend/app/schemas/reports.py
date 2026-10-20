from decimal import Decimal
from typing import Dict, List, Optional
from app.schemas.base import CamelCaseModel


class DashboardSummaryResponse(CamelCaseModel):
    sales_today: Decimal
    orders_today_count: int
    low_stock_count: int
    pending_orders_waiting_count: int
    orders_by_status: Dict[str, int]


class SalesReportItem(CamelCaseModel):
    period: str  # e.g. "2026-10-18" or product/category name
    orders_count: int
    items_sold: int
    total_sales: Decimal
    total_discount: Decimal
    total_delivery_fees: Decimal


class SalesReportResponse(CamelCaseModel):
    items: List[SalesReportItem]
    grand_total_sales: Decimal
    grand_total_orders: int
    grand_total_items: int


class InventoryValuationResponse(CamelCaseModel):
    total_products: int
    total_stock_units: int
    total_retail_value: Decimal
    low_stock_products_count: int
    out_of_stock_products_count: int

