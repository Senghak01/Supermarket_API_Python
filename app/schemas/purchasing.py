import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import EmailStr, Field
from app.models.purchasing import PurchaseStatus
from app.schemas.base import CamelCaseModel


class SupplierCreateRequest(CamelCaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    contact_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class SupplierUpdateRequest(CamelCaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierResponse(CamelCaseModel):
    id: int
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime


class PurchaseOrderItemCreate(CamelCaseModel):
    product_id: int = Field(..., ge=1)
    unit_cost: Decimal = Field(..., ge=0)
    quantity: int = Field(..., ge=1)


class PurchaseOrderItemResponse(CamelCaseModel):
    id: int
    product_id: int
    product_name: str
    sku: str
    unit_cost: Decimal
    quantity: int
    received_quantity: int
    subtotal: Decimal


class PurchaseOrderCreateRequest(CamelCaseModel):
    supplier_id: int = Field(..., ge=1)
    invoice_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    items: List[PurchaseOrderItemCreate] = Field(..., min_length=1)


class PurchaseOrderResponse(CamelCaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    employee_id: int
    employee_name: str
    status: PurchaseStatus
    total_amount: Decimal
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    ordered_at: Optional[datetime.datetime] = None
    received_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    items: List[PurchaseOrderItemResponse] = []

