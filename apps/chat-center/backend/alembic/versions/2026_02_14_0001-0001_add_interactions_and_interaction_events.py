"""Add interactions and interaction_events tables

Revision ID: 0001
Revises:
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### interactions table ###
    op.create_table(
        'interactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('marketplace', sa.String(length=50), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=True),
        sa.Column('order_id', sa.String(length=100), nullable=True),
        sa.Column('nm_id', sa.String(length=100), nullable=True),
        sa.Column('product_article', sa.String(length=100), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('needs_response', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='wb_api'),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], name='fk_interactions_seller_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seller_id', 'marketplace', 'channel', 'external_id', name='uq_interactions_identity'),
    )
    op.create_index('ix_interactions_id', 'interactions', ['id'], unique=False)
    op.create_index('ix_interactions_seller_id', 'interactions', ['seller_id'], unique=False)
    op.create_index('idx_interactions_channel_status', 'interactions', ['seller_id', 'channel', 'status'], unique=False)
    op.create_index('idx_interactions_priority', 'interactions', ['seller_id', 'priority', 'needs_response'], unique=False)
    op.create_index('idx_interactions_occurred', 'interactions', ['seller_id', 'occurred_at'], unique=False)
    op.create_index('idx_interactions_source', 'interactions', ['seller_id', 'source'], unique=False)

    # ### interaction_events table ###
    op.create_table(
        'interaction_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interaction_id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['interaction_id'], ['interactions.id'], name='fk_interaction_events_interaction_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], name='fk_interaction_events_seller_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_interaction_events_id', 'interaction_events', ['id'], unique=False)
    op.create_index('ix_interaction_events_interaction_id', 'interaction_events', ['interaction_id'], unique=False)
    op.create_index('ix_interaction_events_seller_id', 'interaction_events', ['seller_id'], unique=False)
    op.create_index('ix_interaction_events_channel', 'interaction_events', ['channel'], unique=False)
    op.create_index('ix_interaction_events_event_type', 'interaction_events', ['event_type'], unique=False)
    op.create_index('ix_interaction_events_created_at', 'interaction_events', ['created_at'], unique=False)
    op.create_index('idx_interaction_events_seller_created', 'interaction_events', ['seller_id', 'created_at'], unique=False)
    op.create_index('idx_interaction_events_channel_type', 'interaction_events', ['channel', 'event_type'], unique=False)


def downgrade() -> None:
    # ### interaction_events table ###
    op.drop_index('idx_interaction_events_channel_type', table_name='interaction_events')
    op.drop_index('idx_interaction_events_seller_created', table_name='interaction_events')
    op.drop_index('ix_interaction_events_created_at', table_name='interaction_events')
    op.drop_index('ix_interaction_events_event_type', table_name='interaction_events')
    op.drop_index('ix_interaction_events_channel', table_name='interaction_events')
    op.drop_index('ix_interaction_events_seller_id', table_name='interaction_events')
    op.drop_index('ix_interaction_events_interaction_id', table_name='interaction_events')
    op.drop_index('ix_interaction_events_id', table_name='interaction_events')
    op.drop_table('interaction_events')

    # ### interactions table ###
    op.drop_index('idx_interactions_source', table_name='interactions')
    op.drop_index('idx_interactions_occurred', table_name='interactions')
    op.drop_index('idx_interactions_priority', table_name='interactions')
    op.drop_index('idx_interactions_channel_status', table_name='interactions')
    op.drop_index('ix_interactions_seller_id', table_name='interactions')
    op.drop_index('ix_interactions_id', table_name='interactions')
    op.drop_table('interactions')
