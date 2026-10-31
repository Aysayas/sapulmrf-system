"""client keys for resent writes

Revision ID: 71a58b57e6b0
Revises: 47c2c2c5be15
Create Date: 2026-10-31 15:50:05.002410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71a58b57e6b0'
down_revision: Union[str, Sequence[str], None] = '47c2c2c5be15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('deliveries', 'outgoing', 'stock_movements')


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.add_column(table, sa.Column('client_key', sa.String(length=36), nullable=True))
        op.create_unique_constraint(f'{table}_client_key_key', table, ['client_key'])


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.drop_constraint(f'{table}_client_key_key', table, type_='unique')
        op.drop_column(table, 'client_key')
