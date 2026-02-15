"""Add performance indexes for list queries and cross-channel linking

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-14

New indexes:
- idx_interactions_list_main: (seller_id, occurred_at DESC, needs_response)
  Covers the main list_interactions query that filters by seller_id and
  orders by occurred_at DESC, with optional needs_response filter.

- idx_interactions_linking_nm: (seller_id, marketplace, nm_id)
  Covers linking queries that search by product nm_id within a marketplace.

- idx_interactions_linking_customer: (seller_id, marketplace, customer_id)
  Covers linking queries that search by customer_id within a marketplace.

- idx_interactions_linking_order: (seller_id, marketplace, order_id)
  Covers linking queries that search by order_id within a marketplace.

- idx_interactions_needs_response: (seller_id, needs_response, occurred_at DESC)
  Covers the common "needs response" filter in the list query, ordered by recency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Index definitions: (name, table, columns)
_INDEXES = [
    (
        'idx_interactions_list_main',
        'interactions',
        [sa.text('seller_id'), sa.text('occurred_at DESC'), sa.text('needs_response')],
    ),
    (
        'idx_interactions_linking_nm',
        'interactions',
        ['seller_id', 'marketplace', 'nm_id'],
    ),
    (
        'idx_interactions_linking_customer',
        'interactions',
        ['seller_id', 'marketplace', 'customer_id'],
    ),
    (
        'idx_interactions_linking_order',
        'interactions',
        ['seller_id', 'marketplace', 'order_id'],
    ),
    (
        'idx_interactions_needs_response',
        'interactions',
        [sa.text('seller_id'), sa.text('needs_response'), sa.text('occurred_at DESC')],
    ),
]


def _index_exists(connection, index_name: str, table_name: str) -> bool:
    """Check if an index already exists (works for both PostgreSQL and SQLite)."""
    dialect = connection.dialect.name

    if dialect == 'postgresql':
        result = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes WHERE indexname = :name AND tablename = :table"
            ),
            {"name": index_name, "table": table_name},
        )
        return result.fetchone() is not None

    if dialect == 'sqlite':
        result = connection.execute(
            sa.text(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name = :name"
            ),
            {"name": index_name},
        )
        return result.fetchone() is not None

    # Fallback: try to create and let it fail gracefully
    return False


def upgrade() -> None:
    connection = op.get_bind()

    for index_name, table_name, columns in _INDEXES:
        if _index_exists(connection, index_name, table_name):
            continue
        op.create_index(index_name, table_name, columns, unique=False)


def downgrade() -> None:
    for index_name, table_name, _columns in reversed(_INDEXES):
        op.drop_index(index_name, table_name=table_name)
