"""add approved column to users — registration requires admin approval

Revision ID: 016_add_user_approved
Revises: 015_add_users_and_project_owner
Create Date: 2026-07-04 10:00:00.000000

既有使用者一律視為已審核。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '016_add_user_approved'
down_revision = '015_add_users_and_project_owner'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    cols = [c['name'] for c in inspect(op.get_bind()).get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    if not _column_exists('users', 'approved'):
        op.add_column('users', sa.Column('approved', sa.Boolean(), nullable=False, server_default='0'))
        op.get_bind().execute(sa.text("UPDATE users SET approved = 1"))


def downgrade() -> None:
    op.drop_column('users', 'approved')
