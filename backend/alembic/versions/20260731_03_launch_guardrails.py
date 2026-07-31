"""Persistent daily launch limits.

Revision ID: 20260731_03
Revises: 20260731_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20260731_03"
down_revision = "20260731_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_usage",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("usage_date", sa.Text(), nullable=False),
        sa.Column("usage_type", sa.Text(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint(
            "user_id", "usage_date", "usage_type", name="pk_daily_usage"
        ),
        sa.CheckConstraint(
            "usage_type IN ('career_analysis', 'suggestion_generation', "
            "'suggestion_regeneration', 'resume_export')",
            name="ck_daily_usage_type",
        ),
        sa.CheckConstraint("used_count >= 0", name="ck_daily_usage_count"),
    )
    op.create_index(
        "idx_daily_usage_date", "daily_usage", ["usage_date", "usage_type"]
    )


def downgrade() -> None:
    op.drop_table("daily_usage")
