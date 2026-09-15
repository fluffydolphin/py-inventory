# py-inventory

Backend for a small warehouse: products, suppliers, purchase orders, receiving, stock adjustments, and CSV import.

Stock never changes without a `stock_movements` row. Receive and the qty update are one transaction. A second receive with the same idempotency key does not double stock. Bad CSV rows land in `import_errors`; the rest of the file still imports.

## How to run

Docker Desktop running, from this folder:

```powershell
docker compose up --build
```

API: http://127.0.0.1:8000/docs

Example login (seeded on API start):

- email: `admin@example.com`
- password: `admin`

Without Docker, with Postgres already up on `localhost:5432`:

```powershell
uv sync
uv run alembic upgrade head
uv run python scripts/seed_admin.py
uv run fastapi dev app/main.py
uv run pytest -v
```

## Purchase order status

```
draft → submitted → partial → received
              ↘           ↗
               cancelled
```

- **draft** — purchaser creates lines. No stock movement.
- **submitted** — warehouse may receive.
- **partial** — some qty received, remainder still open.
- **received** — every line is fully received.
- **cancelled** — only from draft or submitted. Cannot cancel after stock has been received.

Roles: **purchaser** creates/submits POs. **warehouse** receives and adjusts. **admin** can do both, plus product CSV import.

## Tradeoff

I store `qty_on_hand` on the product and write a movement in the same transaction so reads stay simple (`GET /products`, low-stock). A ledger-only model (`SUM` of movements) cannot drift, but every stock read becomes an aggregate. Same-commit updates keep the two in sync; `FOR UPDATE` on receive/adjust stops two warehouse users from clobbering the same row.

## Example

Login, then create a product (paste the token into Authorize in `/docs`):

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
```

The dangerous cases are in pytest: double receive, receive more than ordered, purchaser hitting receive (403), CSV 100 rows with 3 bad.

## Local notes

`JWT_SECRET` and `DATABASE_URL` can be set as environment variables.
