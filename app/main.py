from fastapi import Depends, FastAPI, HTTPException, status, Query
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    require_admin,
    require_purchaser_or_admin,
    verify_password,
)
from app.db import get_db
from app.models import Product, StockMovement, Supplier, User
from app.routers.imports import router as imports_router
from app.routers.purchase_orders import router as purchase_orders_router
from app.routers.stock import router as stock_router
from app.schemas import (
    LoginIn,
    MovementOut,
    ProductCreate,
    ProductOut,
    SupplierCreate,
    SupplierOut,
    TokenOut,
)

app = FastAPI(title="py-inventory")
app.include_router(purchase_orders_router)
app.include_router(stock_router)
app.include_router(imports_router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        # Same message either way: do not reveal whether the email exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token)


@app.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Product]:
    return list(db.scalars(select(Product).order_by(Product.id).limit(limit).offset(offset)))


@app.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Product:
    product = Product(
        sku=body.sku,
        name=body.name,
        unit=body.unit,
        cost_cents=body.cost_cents,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        # Unique SKU failed. Undo the failed transaction, then tell the client.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU already exists",
        ) from None
    db.refresh(product)
    return product


@app.get("/products/{product_id}/movements", response_model=list[MovementOut])
def list_product_movements(
    product_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[StockMovement]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return list(
        db.scalars(
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.id)
        )
    )


@app.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Supplier]:
    return list(db.scalars(select(Supplier).order_by(Supplier.id)))


@app.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    body: SupplierCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_purchaser_or_admin),
) -> Supplier:
    supplier = Supplier(name=body.name, email=str(body.email))
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier email already exists",
        ) from None
    db.refresh(supplier)
    return supplier
