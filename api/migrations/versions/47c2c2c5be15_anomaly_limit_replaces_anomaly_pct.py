"""anomaly limit replaces anomaly pct

Revision ID: 47c2c2c5be15
Revises: 45e07edaff9a
Create Date: 2026-10-31 07:43:44.980395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47c2c2c5be15'
down_revision: Union[str, Sequence[str], None] = '45e07edaff9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Saved percentages have no equivalent limit, so every row resets to the default."""
    op.add_column('settings', sa.Column('anomaly_limit', sa.Float(), nullable=False, server_default='3.5'))
    op.alter_column('settings', 'anomaly_limit', server_default=None)
    op.drop_column('settings', 'anomaly_pct')


def downgrade() -> None:
    op.add_column('settings', sa.Column('anomaly_pct', sa.Float(), nullable=False, server_default='2'))
    op.alter_column('settings', 'anomaly_pct', server_default=None)
    op.drop_column('settings', 'anomaly_limit')
