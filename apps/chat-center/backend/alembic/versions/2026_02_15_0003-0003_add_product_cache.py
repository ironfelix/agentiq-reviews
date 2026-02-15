"""Add product_cache table

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create product_cache table
    op.create_table(
        'product_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nm_id', sa.String(length=50), nullable=False),
        sa.Column('marketplace', sa.String(length=50), nullable=False, server_default='wb'),
        sa.Column('name', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('brand', sa.String(length=200), nullable=True),
        sa.Column('category', sa.String(length=300), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nm_id', name='uq_product_cache_nm_id'),
    )

    # Create indexes
    op.create_index('ix_product_cache_id', 'product_cache', ['id'], unique=False)
    op.create_index('ix_product_cache_nm_id', 'product_cache', ['nm_id'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_product_cache_nm_id', table_name='product_cache')
    op.drop_index('ix_product_cache_id', table_name='product_cache')

    # Drop table
    op.drop_table('product_cache')
