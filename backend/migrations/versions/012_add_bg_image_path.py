"""add bg_image_path to pages

Revision ID: 012_add_bg_image_path
Revises: 011_add_user_template_thumb
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = '012_add_bg_image_path'
down_revision = '011_add_user_template_thumb'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pages') as batch_op:
        batch_op.add_column(sa.Column('bg_image_path', sa.String(500), nullable=True))


def downgrade():
    with op.batch_alter_table('pages') as batch_op:
        batch_op.drop_column('bg_image_path')
