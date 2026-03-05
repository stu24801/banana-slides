"""add text_regions to pages

Revision ID: 013_add_text_regions
Revises: 012_add_bg_image_path
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = '013_add_text_regions'
down_revision = '012_add_bg_image_path'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pages') as batch_op:
        batch_op.add_column(sa.Column('text_regions', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('pages') as batch_op:
        batch_op.drop_column('text_regions')
