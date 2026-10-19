"""interview rounds, resume text and delivery metrics (Part 9)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-19

Additive only (three nullable / defaulted columns on interview_sessions). Each step checks first,
so it is safe even if the app's startup ensure_columns() already added them.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _existing(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    cols = _existing("interview_sessions")
    if not cols:
        return
    if "round" not in cols:
        op.add_column("interview_sessions", sa.Column("round", sa.String(), nullable=True, server_default="dsa"))
    if "resume_text" not in cols:
        op.add_column("interview_sessions", sa.Column("resume_text", sa.Text(), nullable=True))
    if "delivery_metrics" not in cols:
        op.add_column("interview_sessions", sa.Column("delivery_metrics", sa.Text(), nullable=True))


def downgrade() -> None:
    # Intentionally a no-op: never drop user data.
    pass
