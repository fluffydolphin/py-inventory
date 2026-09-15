"""Create the products table.

This is the same CREATE TABLE as sql/block_a.sql, stored as a migration
so any machine can build the same schema with: alembic upgrade head

Revision ID: 20260914_create_products
Revises:
"""

from alembic import op

# revision identifiers. Alembic uses these to order migrations.
revision = "20260914_create_products"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply this change: create products."""
    op.execute(
        """
        CREATE TABLE products (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            sku        TEXT NOT NULL UNIQUE,
            name       TEXT NOT NULL,
            unit       TEXT NOT NULL,
            cost_cents INTEGER NOT NULL CHECK (cost_cents >= 0),
            active     BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    """Undo this change: drop products."""
    op.execute("DROP TABLE products")
