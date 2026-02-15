"""Add is_auto_response column to interactions table

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_auto_response column with default False
    with op.batch_alter_table('interactions') as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_auto_response',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('0'),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('interactions') as batch_op:
        batch_op.drop_column('is_auto_response')
