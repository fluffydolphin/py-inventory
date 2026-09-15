from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Parent for every table class. SQLAlchemy keeps metadata here."""


class Product(Base):
    # Shape of the products table. Alembic creates/changes the real table.
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sku: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    cost_cents: Mapped[int]
    # Optional. Null means "no low-stock threshold yet."
    reorder_point: Mapped[int | None] = mapped_column(default=None)
    qty_on_hand: Mapped[int] = mapped_column(Integer, server_default="0")
    active: Mapped[bool] = mapped_column(server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    active: Mapped[bool] = mapped_column(server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class Role(StrEnum):
    ADMIN = "admin"
    PURCHASER = "purchaser"
    WAREHOUSE = "warehouse"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    # admin | purchaser | warehouse — CHECK in the migration enforces this.
    role: Mapped[Role] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class PurchaseOrderStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    RECEIVED = "received"
    CANCELLED = "cancelled"

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    po_number: Mapped[str] = mapped_column(Text, unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    status: Mapped[PurchaseOrderStatus] = mapped_column(Text, server_default=PurchaseOrderStatus.DRAFT)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    lines: Mapped[list["PoLine"]] = relationship(back_populates="purchase_order")


class PoLine(Base):
    __tablename__ = "po_lines"
    __table_args__ = (
        UniqueConstraint("po_id", "product_id", name="po_lines_po_id_product_id_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty_ordered: Mapped[int] = mapped_column(Integer)
    qty_received: Mapped[int] = mapped_column(Integer, server_default="0")
    unit_cost_cents: Mapped[int] = mapped_column(Integer)
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class PoReceive(Base):
    """One successful receive against a PO. Unique key makes retries safe."""

    __tablename__ = "po_receives"
    __table_args__ = (
        UniqueConstraint(
            "po_id", "idempotency_key", name="po_receives_po_id_key"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    idempotency_key: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty_delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    ref_type: Mapped[str | None] = mapped_column(Text, default=None)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class ImportJobStatus(StrEnum):
    PENDING = "pending"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    COMPLETED = "completed"

class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    filename: Mapped[str] = mapped_column(Text)
    status: Mapped[ImportJobStatus] = mapped_column(Text)
    imported_count: Mapped[int] = mapped_column(Integer, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ImportJobError(Base):
    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    raw_row: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
