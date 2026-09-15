"""Create the users table.

Revision ID: 20260914_create_users
Revises: 6f5fcca1d6ab
"""

from alembic import op

revision = "20260914_create_users"
down_revision = "6f5fcca1d6ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL CHECK (role IN ('admin', 'purchaser', 'warehouse')),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE users")
