from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, require_purchaser_or_admin, require_warehouse_or_admin
from app.db import get_db
from app.models import PoLine, PoReceive, Product, PurchaseOrder, StockMovement, Supplier, User, PurchaseOrderStatus
from app.schemas import PurchaseOrderCreate, PurchaseOrderOut, ReceiveIn

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _load_po(db: Session, po_id: int) -> PurchaseOrder | None:
    return db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.id == po_id)
    )


@router.post("", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    body: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_purchaser_or_admin),
) -> PurchaseOrder:
    product_ids = [line.product_id for line in body.lines]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate product on one PO",
        )

    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    if not supplier.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier is inactive",
        )

    for line in body.lines:
        product = db.get(Product, line.product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {line.product_id} not found",
            )
        if not product.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product.sku} is inactive",
            )

    # Temporary unique po_number so NOT NULL + UNIQUE are happy before we know id.
    po = PurchaseOrder(
        po_number=f"tmp-{actor.id}-{datetime.now(timezone.utc).timestamp()}",
        supplier_id=supplier.id,
        status=PurchaseOrderStatus.DRAFT,
        created_by=actor.id,
    )
    db.add(po)
    db.flush()
    po.po_number = f"PO-{datetime.now(timezone.utc).year}-{po.id:05d}"
    for line in body.lines:
        db.add(
            PoLine(
                po_id=po.id,
                product_id=line.product_id,
                qty_ordered=line.qty_ordered,
                unit_cost_cents=line.unit_cost_cents,
            )
        )
    db.commit()
    loaded = _load_po(db, po.id)
    assert loaded is not None
    return loaded


@router.get("", response_model=list[PurchaseOrderOut])
def list_purchase_orders(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    supplier_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PurchaseOrder]:
    if status_filter is not None and status_filter not in PurchaseOrderStatus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status",
        )
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.id)
    )
    if status_filter is not None:
        stmt = stmt.where(PurchaseOrder.status == status_filter)
    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PurchaseOrder:
    po = _load_po(db, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.post("/{po_id}/submit", response_model=PurchaseOrderOut)
def submit_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_purchaser_or_admin),
) -> PurchaseOrder:
    po = _load_po(db, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status != PurchaseOrderStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a draft PO can be submitted",
        )
    po.status = PurchaseOrderStatus.SUBMITTED
    po.submitted_at = datetime.now(timezone.utc)
    db.commit()
    loaded = _load_po(db, po.id)
    assert loaded is not None
    return loaded


@router.post("/{po_id}/cancel", response_model=PurchaseOrderOut)
def cancel_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_purchaser_or_admin),
) -> PurchaseOrder:
    po = _load_po(db, po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status in (PurchaseOrderStatus.PARTIAL, PurchaseOrderStatus.RECEIVED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel after stock has been received",
        )
    if po.status == PurchaseOrderStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PO is already cancelled",
        )
    po.status = PurchaseOrderStatus.CANCELLED
    db.commit()
    loaded = _load_po(db, po.id)
    assert loaded is not None
    return loaded


@router.post("/{po_id}/receive", response_model=PurchaseOrderOut)
def receive_purchase_order(
    po_id: int,
    body: ReceiveIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_warehouse_or_admin),
) -> PurchaseOrder:
    # Lock the PO so two receives cannot interleave on the same document.
    po = db.scalar(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update()
    )
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")

    already = db.scalar(
        select(PoReceive).where(
            PoReceive.po_id == po_id,
            PoReceive.idempotency_key == body.idempotency_key,
        )
    )
    if already is not None:
        loaded = _load_po(db, po_id)
        assert loaded is not None
        return loaded

    if po.status not in (PurchaseOrderStatus.SUBMITTED, PurchaseOrderStatus.PARTIAL):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only submitted or partial POs can be received",
        )

    line_ids = [item.po_line_id for item in body.lines]
    if len(line_ids) != len(set(line_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate po_line_id in receive",
        )

    po_lines = list(
        db.scalars(select(PoLine).where(PoLine.po_id == po_id).with_for_update())
    )
    line_by_id = {line.id: line for line in po_lines}

    for item in body.lines:
        line = line_by_id.get(item.po_line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PO line {item.po_line_id} is not on this PO",
            )
        remaining = line.qty_ordered - line.qty_received
        if item.qty > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot receive more than ordered",
            )

    product_ids = {line_by_id[item.po_line_id].product_id for item in body.lines}
    products = list(
        db.scalars(select(Product).where(Product.id.in_(product_ids)).with_for_update())
    )
    product_by_id = {product.id: product for product in products}

    receive = PoReceive(
        po_id=po.id,
        idempotency_key=body.idempotency_key,
        created_by=actor.id,
    )
    db.add(receive)
    db.flush()

    for item in body.lines:
        line = line_by_id[item.po_line_id]
        line.qty_received += item.qty
        product = product_by_id[line.product_id]
        product.qty_on_hand += item.qty
        db.add(
            StockMovement(
                product_id=product.id,
                qty_delta=item.qty,
                reason="po_receive",
                ref_type="po_receive",
                ref_id=receive.id,
                created_by=actor.id,
            )
        )

    if all(line.qty_received == line.qty_ordered for line in po_lines):
        po.status = PurchaseOrderStatus.RECEIVED
        po.received_at = datetime.now(timezone.utc)
    else:
        po.status = PurchaseOrderStatus.PARTIAL

    db.commit()
    loaded = _load_po(db, po.id)
    assert loaded is not None
    return loaded
