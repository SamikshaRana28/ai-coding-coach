"""create checkins + notifications, add users.notify_email (Part 6)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19

Additive only. Each step checks first, so it is safe to run even if the app's startup
create_all()/ensure_columns() already created the table or column.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("checkins"):
        op.create_table(
            "checkins",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("mood", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("tasks_done", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tasks_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "date", name="uq_checkins_user_date"),
        )
        op.create_index("ix_checkins_user_id", "checkins", ["user_id"])

    if not insp.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("dedupe_key", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    if insp.has_table("users") and "notify_email" not in {c["name"] for c in insp.get_columns("users")}:
        op.add_column("users", sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("users") and "notify_email" in {c["name"] for c in insp.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("notify_email")
    for table in ("notifications", "checkins"):
        if insp.has_table(table):
            op.drop_table(table)
