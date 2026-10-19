"""create study_plans, daily_tasks, user_streaks (Part 5)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19

Every table is only created if it is missing (the app's startup create_all() may have made it
already), so `alembic upgrade head` never fails on a dev/prod database that ran the new code first.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("study_plans"):
        op.create_table(
            "study_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("focus_topics", sa.JSON(), nullable=True),
            sa.Column("goal", sa.Text(), nullable=True),
            sa.Column("minutes_per_day", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("review", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_study_plans_user_id", "study_plans", ["user_id"])

    if not insp.has_table("daily_tasks"):
        op.create_table(
            "daily_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), sa.ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("problem_id", sa.Integer(), sa.ForeignKey("problems.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_daily_tasks_user_id", "daily_tasks", ["user_id"])
        op.create_index("ix_daily_tasks_plan_id", "daily_tasks", ["plan_id"])

    if not insp.has_table("user_streaks"):
        op.create_table(
            "user_streaks",
            sa.Column("user_id", sa.Integer(), primary_key=True),
            sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_active_date", sa.Date(), nullable=True),
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for table in ("user_streaks", "daily_tasks", "study_plans"):     # children first
        if insp.has_table(table):
            op.drop_table(table)
