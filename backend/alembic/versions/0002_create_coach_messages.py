"""create coach_messages table

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("coach_messages"):
        op.create_table(
            "coach_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tool_calls", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_coach_messages_user_id", "coach_messages", ["user_id"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("coach_messages"):
        op.drop_table("coach_messages")
