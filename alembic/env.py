from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db import DATABASE_URL
from app.models import Base

# Reads alembic.ini. We override the URL so it stays in one place: app/db.py.
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate diffs this metadata against the live database.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Print SQL without connecting. We use online mode in this project."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and run upgrade() / downgrade() against Postgres."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
