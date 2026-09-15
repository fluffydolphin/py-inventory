"""Add products.reorder_point.

Autogenerate also wanted to alter created_at (TIMESTAMPTZ vs DateTime).
That was a model mismatch, not a real change. Always read this file.

Revision ID: 6f5fcca1d6ab
Revises: 20260914_create_products
"""

from alembic import op
import sqlalchemy as sa

revision = "6f5fcca1d6ab"
down_revision = "20260914_create_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("reorder_point", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "reorder_point")
