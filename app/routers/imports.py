import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.models import ImportJob, ImportJobError, Product, StockMovement, User
from app.schemas import ImportErrorOut, ImportJobOut

router = APIRouter(tags=["imports"])

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
REQUIRED_HEADERS = ("sku", "name", "unit", "cost_cents")


def _raw(values: list[str]) -> str:
    return ",".join(values)


def _parse_non_negative_int(value: str, field: str) -> int:
    try:
        number = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer >= 0") from exc
    if number < 0:
        raise ValueError(f"{field} must be an integer >= 0")
    return number


@router.post("/imports/products", response_model=ImportJobOut)
def import_products(
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
    file: UploadFile = File(...),
) -> ImportJob:
    payload = file.file.read(MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV must be 2MB or smaller",
        )
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must be UTF-8",
        ) from None

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV is empty",
        ) from None

    header_map = {name.strip().lower(): index for index, name in enumerate(header)}
    missing = [name for name in REQUIRED_HEADERS if name not in header_map]
    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV has more than {MAX_ROWS} rows",
        )

    job = ImportJob(
        filename=file.filename or "products.csv",
        status="pending",
        created_by=actor.id,
    )
    db.add(job)
    db.flush()

    if missing:
        db.add(
            ImportJobError(
                job_id=job.id,
                row_number=1,
                raw_row=_raw(header),
                message=f"Missing columns: {', '.join(missing)}",
            )
        )
        job.status = "completed_with_errors"
        job.error_count = 1
        db.commit()
        db.refresh(job)
        return job

    imported = 0
    errors = 0
    seen_skus: set[str] = set()

    for row_number, values in enumerate(rows, start=2):
        raw_row = _raw(values)

        def add_error(message: str) -> None:
            nonlocal errors
            db.add(
                ImportJobError(
                    job_id=job.id,
                    row_number=row_number,
                    raw_row=raw_row,
                    message=message,
                )
            )
            errors += 1

        def cell(name: str) -> str:
            index = header_map[name]
            if index >= len(values):
                return ""
            return values[index].strip()

        sku = cell("sku")
        name = cell("name")
        unit = cell("unit")
        cost_raw = cell("cost_cents")
        opening_raw = ""
        if "opening_qty" in header_map:
            opening_raw = cell("opening_qty")

        if not sku:
            add_error("sku is required")
            continue
        if sku in seen_skus:
            add_error("Duplicate SKU in this file")
            continue
        if not name:
            add_error("name is required")
            continue
        if not unit:
            add_error("unit is required")
            continue
        try:
            cost_cents = _parse_non_negative_int(cost_raw, "cost_cents")
            opening_qty = (
                _parse_non_negative_int(opening_raw, "opening_qty")
                if opening_raw
                else 0
            )
        except ValueError as exc:
            add_error(str(exc))
            continue

        seen_skus.add(sku)
        try:
            with db.begin_nested():
                product = Product(
                    sku=sku,
                    name=name,
                    unit=unit,
                    cost_cents=cost_cents,
                    qty_on_hand=opening_qty,
                )
                db.add(product)
                db.flush()
                if opening_qty > 0:
                    db.add(
                        StockMovement(
                            product_id=product.id,
                            qty_delta=opening_qty,
                            reason="import",
                            ref_type="import_job",
                            ref_id=job.id,
                            created_by=actor.id,
                        )
                    )
                    db.flush()
            imported += 1
        except IntegrityError:
            add_error("SKU already exists")

    job.imported_count = imported
    job.error_count = errors
    job.status = "completed_with_errors" if errors else "completed"
    db.commit()
    db.refresh(job)
    return job


@router.get("/imports/{job_id}", response_model=ImportJobOut)
def get_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return job


@router.get("/imports/{job_id}/errors", response_model=list[ImportErrorOut])
def list_import_errors(
    job_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ImportJobError]:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return list(
        db.scalars(
            select(ImportJobError)
            .where(ImportJobError.job_id == job_id)
            .order_by(ImportJobError.row_number)
            .limit(limit)
            .offset(offset)
        )
    )
