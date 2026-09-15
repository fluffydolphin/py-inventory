"""Add qty_on_hand, po_receives, and stock_movements.

Revision ID: 20260915_receive_stock
Revises: 20260914_create_purchase_orders
"""

from alembic import op

revision = "20260915_receive_stock"
down_revision = "20260914_create_purchase_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE products
        ADD COLUMN qty_on_hand INTEGER NOT NULL DEFAULT 0
        CHECK (qty_on_hand >= 0)
        """
    )
    op.execute(
        """
        CREATE TABLE po_receives (
            id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            po_id           BIGINT NOT NULL REFERENCES purchase_orders(id),
            idempotency_key TEXT NOT NULL,
            created_by      BIGINT NOT NULL REFERENCES users(id),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (po_id, idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE stock_movements (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            product_id BIGINT NOT NULL REFERENCES products(id),
            qty_delta  INTEGER NOT NULL,
            reason     TEXT NOT NULL
                       CHECK (reason IN ('po_receive', 'adjustment', 'import')),
            ref_type   TEXT,
            ref_id     BIGINT,
            created_by BIGINT NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE stock_movements")
    op.execute("DROP TABLE po_receives")
    op.execute("ALTER TABLE products DROP COLUMN qty_on_hand")
