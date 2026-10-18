"""create problems and user_problems

Revision ID: 0001_problems
Revises: 0001_auth_foundation
Create Date: 2026-10-16

Adds the Problems feature tables. Each table is only created if it is missing:
the app's startup create_all() may already have created it on a dev database that
ran the new code before this migration, and `alembic upgrade head` must not fail there.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_problems"
down_revision = "0001_auth_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("problems"):
        op.create_table(
            "problems",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("difficulty", sa.String(), nullable=False),
            sa.Column("topics", sa.JSON(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("url", sa.String(), nullable=True),
            sa.Column("acceptance_rate", sa.Float(), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="leetcode"),
        )
        op.create_index("ix_problems_slug", "problems", ["slug"], unique=True)
        op.create_index("ix_problems_difficulty", "problems", ["difficulty"])

    if not inspector.has_table("user_problems"):
        op.create_table(
            "user_problems",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "problem_id", sa.Integer(),
                sa.ForeignKey("problems.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="todo"),
            sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_code", sa.Text(), nullable=True),
            sa.Column("solved_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "problem_id", name="uq_user_problems_user_problem"),
        )
        op.create_index("ix_user_problems_user_id", "user_problems", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_problems")
    op.drop_table("problems")
