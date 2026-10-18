"""create hint_events table (Part 4: hint system)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-18

One row per (user, problem, level). Only created if missing, so a dev database where
the app's startup create_all() already made it does not break `alembic upgrade head`.
user_problems.hints_used already exists (added in 0001_problems), so nothing to alter there.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("hint_events"):
        op.create_table(
            "hint_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("problem_id", sa.Integer(), sa.ForeignKey("problems.id", ondelete="CASCADE"), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("hint_text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "problem_id", "level", name="uq_hint_events_user_problem_level"),
        )
        op.create_index("ix_hint_events_user_id", "hint_events", ["user_id"])
        op.create_index("ix_hint_events_problem_id", "hint_events", ["problem_id"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("hint_events"):
        op.drop_table("hint_events")
