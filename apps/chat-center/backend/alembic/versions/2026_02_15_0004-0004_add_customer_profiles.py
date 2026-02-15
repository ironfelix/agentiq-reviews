"""Add customer_profiles table

Revision ID: 0004
Revises: 0002
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### customer_profiles table ###
    op.create_table(
        'customer_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('marketplace', sa.String(length=50), nullable=False, server_default='wb'),
        sa.Column('customer_id', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=300), nullable=True),
        sa.Column('total_interactions', sa.Integer(), server_default='0'),
        sa.Column('total_reviews', sa.Integer(), server_default='0'),
        sa.Column('total_questions', sa.Integer(), server_default='0'),
        sa.Column('total_chats', sa.Integer(), server_default='0'),
        sa.Column('avg_rating', sa.Float(), nullable=True),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sentiment_trend', sa.String(length=20), server_default='neutral'),
        sa.Column('recent_sentiment_scores', sa.JSON(), nullable=True),
        sa.Column('is_repeat_complainer', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('is_vip', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], name='fk_customer_profiles_seller_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seller_id', 'marketplace', 'customer_id', name='uq_customer_profile'),
    )
    op.create_index('ix_customer_profiles_id', 'customer_profiles', ['id'], unique=False)
    op.create_index('ix_customer_profiles_customer_id', 'customer_profiles', ['customer_id'], unique=False)
    op.create_index('idx_customer_profiles_seller', 'customer_profiles', ['seller_id', 'marketplace'], unique=False)


def downgrade() -> None:
    # ### customer_profiles table ###
    op.drop_index('idx_customer_profiles_seller', table_name='customer_profiles')
    op.drop_index('ix_customer_profiles_customer_id', table_name='customer_profiles')
    op.drop_index('ix_customer_profiles_id', table_name='customer_profiles')
    op.drop_table('customer_profiles')
