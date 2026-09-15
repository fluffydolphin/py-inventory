from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    active: bool
    created_at: datetime


class ProductCreate(BaseModel):
    """Body for POST /products. FastAPI validates this before our route runs."""

    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    cost_cents: int = Field(ge=0)


class ProductOut(BaseModel):
    # from_attributes: build this from a Product ORM object, not only a dict.
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    unit: str
    cost_cents: int
    reorder_point: int | None
    qty_on_hand: int
    active: bool
    created_at: datetime


class PoLineIn(BaseModel):
    product_id: int
    qty_ordered: int = Field(gt=0)
    unit_cost_cents: int = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    lines: list[PoLineIn] = Field(min_length=1)


class PoLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty_ordered: int
    qty_received: int
    unit_cost_cents: int


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier_id: int
    status: str
    created_by: int
    created_at: datetime
    submitted_at: datetime | None
    received_at: datetime | None
    lines: list[PoLineOut]


class ReceiveLineIn(BaseModel):
    po_line_id: int
    qty: int = Field(gt=0)


class ReceiveIn(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    lines: list[ReceiveLineIn] = Field(min_length=1)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty_delta: int
    reason: str
    ref_type: str | None
    ref_id: int | None
    created_by: int
    created_at: datetime


class AdjustmentIn(BaseModel):
    product_id: int
    qty_delta: int
    reason: str = Field(min_length=1, max_length=40)


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    imported_count: int
    error_count: int
    created_by: int
    created_at: datetime


class ImportErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    row_number: int
    raw_row: str
    message: str
