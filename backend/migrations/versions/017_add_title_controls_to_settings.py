"""add show_page_title and title_emphasis to settings table

Revision ID: 017_add_title_controls
Revises: 016_add_user_approved
Create Date: 2026-07-31 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '017_add_title_controls'
down_revision = '016_add_user_approved'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('settings', 'show_page_title'):
        op.add_column('settings', sa.Column('show_page_title', sa.Boolean(), nullable=False, server_default='1'))
    if not _column_exists('settings', 'title_emphasis'):
        op.add_column('settings', sa.Column('title_emphasis', sa.String(length=20), nullable=False, server_default='medium'))


def downgrade() -> None:
    op.drop_column('settings', 'title_emphasis')
    op.drop_column('settings', 'show_page_title')
