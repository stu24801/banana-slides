"""add cover_page_enabled to projects table

Revision ID: 014_add_cover_page_enabled
Revises: 38292967f3ca
Create Date: 2026-06-22 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '014_add_cover_page_enabled'
down_revision = '013_add_text_regions'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('projects', 'cover_page_enabled'):
        op.add_column('projects', sa.Column('cover_page_enabled', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('projects', 'cover_page_enabled')
