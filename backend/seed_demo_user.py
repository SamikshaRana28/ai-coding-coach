"""
Create (or repair) the demo user with id=1 so the pre-auth demo data
(attempts / topic_progress / progress_history stored under user_id=1) stays visible.

Usage (from backend/, after `alembic upgrade head`):
    DEMO_PASSWORD='choose-a-password' python seed_demo_user.py
    DEMO_PASSWORD='new-password' python seed_demo_user.py --reset-password

Env vars:
    DEMO_PASSWORD   required, min 8 chars. Never hard-coded in the repo.
    DEMO_EMAIL      default: demo@example.com
    DEMO_NAME       default: Demo User

Safe to re-run. It never deletes anything and never overwrites an existing
password unless --reset-password is passed.
"""
import os
import sys

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from auth import DEFAULT_TIMEZONE, hash_password
from models import SessionLocal, User

DEMO_USER_ID = 1


def seed_demo_user(
    db: Session,
    email: str,
    password: str,
    name: str = "Demo User",
    reset_password: bool = False,
) -> str:
    """Returns 'created', 'updated' or 'unchanged'."""
    email = email.strip().lower()
    if len(password) < 8:
        raise ValueError("DEMO_PASSWORD must be at least 8 characters")

    clash = (
        db.query(User)
        .filter(func.lower(User.email) == email, User.id != DEMO_USER_ID)
        .first()
    )
    if clash:
        raise ValueError(f"Another user (id={clash.id}) already uses {email}; choose a different DEMO_EMAIL")

    user = db.get(User, DEMO_USER_ID)
    if user is None:
        first, _, last = name.partition(" ")
        db.add(
            User(
                id=DEMO_USER_ID,
                email=email,
                password_hash=hash_password(password),
                name=name,
                first_name=first,
                last_name=last or None,
                timezone=DEFAULT_TIMEZONE,
            )
        )
        status = "created"
    else:
        changed = False
        if not user.email:
            user.email = email
            changed = True
        if not user.name:
            user.name = name
            user.first_name, _, last = name.partition(" ")
            user.last_name = last or None
            changed = True
        if not user.timezone:
            user.timezone = DEFAULT_TIMEZONE
            changed = True
        if not user.password_hash or reset_password:
            user.password_hash = hash_password(password)
            changed = True
        status = "updated" if changed else "unchanged"
    db.commit()

    # We inserted an explicit id, so make the Postgres sequence continue after it;
    # otherwise the next signup would try id=1 and fail.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM users))"
            )
        )
        db.commit()
    return status


def main() -> int:
    password = os.getenv("DEMO_PASSWORD", "")
    if not password:
        print("Set DEMO_PASSWORD (min 8 chars) in the environment first.", file=sys.stderr)
        return 1
    email = os.getenv("DEMO_EMAIL", "demo@example.com")
    name = os.getenv("DEMO_NAME", "Demo User")
    with SessionLocal() as db:
        try:
            status = seed_demo_user(db, email, password, name, reset_password="--reset-password" in sys.argv)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print(f"Demo user id={DEMO_USER_ID} {status} (email: {email.strip().lower()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
