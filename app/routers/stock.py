from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_warehouse_or_admin
from app.db import get_db
from app.models import Product, StockMovement, User
from app.schemas import AdjustmentIn, ProductOut

router = APIRouter(tags=["stock"])

ADJUSTMENT_REASONS = ("damaged", "cycle_count")


@router.post("/stock/adjustments", response_model=ProductOut)
def adjust_stock(
    body: AdjustmentIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_warehouse_or_admin),
) -> Product:
    if body.qty_delta == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="qty_delta cannot be 0",
        )
    if body.reason not in ADJUSTMENT_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason must be damaged or cycle_count",
        )

    product = db.scalar(
        select(Product).where(Product.id == body.product_id).with_for_update()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    new_qty = product.qty_on_hand + body.qty_delta
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity cannot go below zero",
        )

    product.qty_on_hand = new_qty
    db.add(
        StockMovement(
            product_id=product.id,
            qty_delta=body.qty_delta,
            reason="adjustment",
            ref_type=body.reason,
            ref_id=None,
            created_by=actor.id,
        )
    )
    db.commit()
    db.refresh(product)
    return product


@router.get("/stock", response_model=list[ProductOut])
def list_stock(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    low_stock: bool = Query(default=False),
) -> list[Product]:
    stmt = select(Product).order_by(Product.id)
    if low_stock:
        stmt = stmt.where(
            Product.reorder_point.is_not(None),
            Product.qty_on_hand <= Product.reorder_point,
        )
    return list(db.scalars(stmt))
