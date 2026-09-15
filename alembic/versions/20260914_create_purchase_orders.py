"""Create purchase_orders and po_lines.

Revision ID: 20260914_create_purchase_orders
Revises: 20260914_create_suppliers
"""

from alembic import op

revision = "20260914_create_purchase_orders"
down_revision = "20260914_create_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE purchase_orders (
            id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            po_number     TEXT NOT NULL UNIQUE,
            supplier_id   BIGINT NOT NULL REFERENCES suppliers(id),
            status        TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN (
                              'draft', 'submitted', 'partial', 'received', 'cancelled'
                          )),
            created_by    BIGINT NOT NULL REFERENCES users(id),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            submitted_at  TIMESTAMPTZ,
            received_at   TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE po_lines (
            id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            po_id           BIGINT NOT NULL REFERENCES purchase_orders(id),
            product_id      BIGINT NOT NULL REFERENCES products(id),
            qty_ordered     INTEGER NOT NULL CHECK (qty_ordered > 0),
            qty_received    INTEGER NOT NULL DEFAULT 0
                            CHECK (qty_received >= 0 AND qty_received <= qty_ordered),
            unit_cost_cents INTEGER NOT NULL CHECK (unit_cost_cents >= 0),
            UNIQUE (po_id, product_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE po_lines")
    op.execute("DROP TABLE purchase_orders")
