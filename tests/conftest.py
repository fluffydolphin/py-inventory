from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.db import get_db
from app.main import app
from app.models import Base, PoLine, Product, PurchaseOrder, Supplier, User

# Separate database so tests never touch the rows you created in /docs.
TEST_URL = "postgresql+psycopg://inventory:inventory@localhost:5432/inventory_test"
ADMIN_URL = "postgresql+psycopg://inventory:inventory@localhost:5432/postgres"


def _ensure_test_database() -> None:
    # CREATE DATABASE cannot run inside a normal transaction.
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'inventory_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE inventory_test"))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    """One engine for the whole pytest process. Builds the test schema."""
    _ensure_test_database()
    engine = create_engine(TEST_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Session:
    """Empty tables for this test, then close."""
    session = sessionmaker(bind=engine)()
    session.execute(
        text(
            "TRUNCATE import_errors, import_jobs, stock_movements, po_receives, "
            "po_lines, purchase_orders, products, users, suppliers "
            "RESTART IDENTITY CASCADE"
        )
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """HTTP client that uses the test session instead of the real get_db."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(db: Session, email: str, password: str, role: str) -> User:
    user = User(email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db: Session) -> User:
    return _create_user(db, "admin@test.com", "secret", "admin")


@pytest.fixture
def purchaser_user(db: Session) -> User:
    return _create_user(db, "buyer@test.com", "secret", "purchaser")


@pytest.fixture
def warehouse_user(db: Session) -> User:
    return _create_user(db, "warehouse@test.com", "secret", "warehouse")


@pytest.fixture
def admin_client(client: TestClient, admin_user: User) -> TestClient:
    response = client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "secret"},
    )
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def purchaser_client(client: TestClient, purchaser_user: User) -> TestClient:
    response = client.post(
        "/auth/login",
        json={"email": "buyer@test.com", "password": "secret"},
    )
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def warehouse_client(client: TestClient, warehouse_user: User) -> TestClient:
    response = client.post(
        "/auth/login",
        json={"email": "warehouse@test.com", "password": "secret"},
    )
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def product(db: Session) -> Product:
    item = Product(sku="BOLT-M8", name="M8 hex bolt", unit="ea", cost_cents=25)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def stocked_product(db: Session, product: Product) -> Product:
    product.qty_on_hand = 10
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def supplier(db: Session) -> Supplier:
    item = Supplier(name="Acme Fasteners", email="acme@example.com")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def submitted_po(db: Session, purchaser_user: User, supplier: Supplier, product: Product):
    """Submitted PO with qty_ordered=10, ready for warehouse receive."""
    po = PurchaseOrder(
        po_number="tmp-test",
        supplier_id=supplier.id,
        status="submitted",
        created_by=purchaser_user.id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(po)
    db.flush()
    po.po_number = f"PO-2026-{po.id:05d}"
    line = PoLine(
        po_id=po.id,
        product_id=product.id,
        qty_ordered=10,
        unit_cost_cents=25,
    )
    db.add(line)
    db.commit()
    db.refresh(po)
    db.refresh(line)
    return po, line
