"""Create the suppliers table.

Revision ID: 20260914_create_suppliers
Revises: 20260914_create_users
"""

from alembic import op

revision = "20260914_create_suppliers"
down_revision = "20260914_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE suppliers (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            active     BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE suppliers")
