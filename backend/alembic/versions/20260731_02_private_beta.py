"""Invitation-only private beta schema.

Revision ID: 20260731_02
Revises: 20260730_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260731_02"
down_revision = "20260730_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_used_at", sa.Text()),
        sa.CheckConstraint("max_uses > 0", name="ck_invite_codes_max_uses"),
        sa.CheckConstraint("used_count >= 0", name="ck_invite_codes_used_count"),
    )
    op.create_index("idx_invite_codes_active_expiry", "invite_codes", ["is_active", "expires_at"])


def downgrade() -> None:
    op.drop_table("invite_codes")
