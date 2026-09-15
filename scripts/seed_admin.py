"""Create a local admin if one does not exist.

From the project folder, with Postgres up:
    uv run python scripts/seed_admin.py

Login: admin@example.com  /  admin
Local only. Never use this password on a live URL.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Role, User

EMAIL = "admin@example.com"
PASSWORD = "admin"


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == EMAIL))
        if existing is not None:
            print(f"{EMAIL} already exists (role={existing.role})")
            return
        user = User(
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            role=Role.ADMIN,
        )
        db.add(user)
        db.commit()
        print(f"Created {EMAIL} / {PASSWORD} (admin)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
