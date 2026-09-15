import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://inventory:inventory@localhost:5432/inventory")
SQL_ECHO = os.environ.get("SQL_ECHO", "1") not in ("0", "false", "False")

# Engine = the connection factory. One per process.
engine = create_engine(DATABASE_URL, echo=SQL_ECHO)

# Session = one short conversation with the database (one request).
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: open a session, yield it, always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
