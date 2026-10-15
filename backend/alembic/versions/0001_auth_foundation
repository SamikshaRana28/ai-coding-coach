"""auth foundation: password/name/timezone columns on users

Revision ID: 0001_auth_foundation
Revises:
Create Date: 2026-10-15

ADDITIVE and IDEMPOTENT:
  * `users` already exists on deployed databases (id, username, email, created_at).
    We only ADD the missing nullable columns; nothing is dropped, renamed or rewritten.
  * On a blank database `users` is created with the full column set.
  * A unique index on lower(email) is added as a safety net (skipped with a
    warning if existing rows would violate it).
Existing tables (attempts, topic_progress, progress_history, leetcode_users) are not touched.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_auth_foundation"
down_revision = None
branch_labels = None
depends_on = None

NEW_COLUMNS = [
    ("password_hash", lambda: sa.Column("password_hash", sa.String(), nullable=True)),
    ("name", lambda: sa.Column("name", sa.String(), nullable=True)),
    ("first_name", lambda: sa.Column("first_name", sa.String(), nullable=True)),
    ("last_name", lambda: sa.Column("last_name", sa.String(), nullable=True)),
    (
        "timezone",
        lambda: sa.Column(
            "timezone", sa.String(), nullable=True, server_default="Asia/Kolkata"
        ),
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(), unique=True),
            sa.Column("email", sa.String(), unique=True),
            sa.Column("created_at", sa.DateTime()),
            *[make() for _, make in NEW_COLUMNS],
        )
    else:
        existing = {c["name"] for c in inspector.get_columns("users")}
        for name, make in NEW_COLUMNS:
            if name not in existing:
                op.add_column("users", make())

    # Case-insensitive uniqueness backstop (the app always stores lowercase).
    dupes = bind.execute(
        sa.text(
            "SELECT lower(email) FROM users WHERE email IS NOT NULL "
            "GROUP BY lower(email) HAVING count(*) > 1"
        )
    ).fetchall()
    if dupes:
        print(
            "WARNING: skipping ix_users_email_lower - existing users share an email "
            "ignoring case. Resolve the duplicates manually, then re-run."
        )
    else:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_lower ON users (lower(email))"
        )


def downgrade() -> None:
    # Intentionally non-destructive: we only remove the index. The added columns
    # hold user data (password hashes, names) and are kept on purpose.
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
