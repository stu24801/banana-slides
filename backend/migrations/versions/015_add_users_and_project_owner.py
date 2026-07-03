"""add users table and project user_id owner column

Revision ID: 015_add_users_and_project_owner
Revises: 014_add_cover_page_enabled
Create Date: 2026-07-03 09:00:00.000000

既有專案全部歸屬給預設 admin 帳號（密碼取 ADMIN_PASSWORD 環境變數，未設定則為 admin123，請登入後盡快修改）。
"""
import os
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash


revision = '015_add_users_and_project_owner'
down_revision = '014_add_cover_page_enabled'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    cols = [c['name'] for c in inspect(op.get_bind()).get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    if not _table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('username', sa.String(64), nullable=False, unique=True, index=True),
            sa.Column('password_hash', sa.String(256), nullable=False),
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if not _column_exists('projects', 'user_id'):
        op.add_column('projects', sa.Column('user_id', sa.String(36), nullable=True))
        op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # 建立預設 admin 並收編既有專案
    bind = op.get_bind()
    existing = bind.execute(sa.text("SELECT id FROM users WHERE username = 'admin'")).fetchone()
    if existing:
        admin_id = existing[0]
    else:
        admin_id = str(uuid.uuid4())
        password = os.getenv('ADMIN_PASSWORD', 'admin123')
        bind.execute(
            sa.text("INSERT INTO users (id, username, password_hash, is_admin, created_at) "
                    "VALUES (:id, 'admin', :ph, 1, CURRENT_TIMESTAMP)"),
            {'id': admin_id, 'ph': generate_password_hash(password)},
        )
    bind.execute(
        sa.text("UPDATE projects SET user_id = :uid WHERE user_id IS NULL"),
        {'uid': admin_id},
    )


def downgrade() -> None:
    op.drop_index('ix_projects_user_id', 'projects')
    op.drop_column('projects', 'user_id')
    op.drop_table('users')
