"""Create import_jobs and import_errors.

Revision ID: 20260915_product_csv_import
Revises: 20260915_receive_stock
"""

from alembic import op

revision = "20260915_product_csv_import"
down_revision = "20260915_receive_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE import_jobs (
            id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            filename       TEXT NOT NULL,
            status         TEXT NOT NULL
                           CHECK (status IN (
                               'pending', 'completed', 'completed_with_errors'
                           )),
            imported_count INTEGER NOT NULL DEFAULT 0,
            error_count    INTEGER NOT NULL DEFAULT 0,
            created_by     BIGINT NOT NULL REFERENCES users(id),
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE import_errors (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            job_id     BIGINT NOT NULL REFERENCES import_jobs(id),
            row_number INTEGER NOT NULL,
            raw_row    TEXT NOT NULL,
            message    TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE import_errors")
    op.execute("DROP TABLE import_jobs")
