"""operator profile contact, anomaly pct

Revision ID: 45e07edaff9a
Revises: d19b985ccd91
Create Date: 2026-10-31 03:41:19.939315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45e07edaff9a'
down_revision: Union[str, Sequence[str], None] = 'd19b985ccd91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Server defaults fill the rows that already exist, then come off to match the models.
    op.add_column('settings', sa.Column('anomaly_pct', sa.Float(), nullable=False, server_default='2'))
    op.alter_column('settings', 'anomaly_pct', server_default=None)
    op.drop_column('settings', 'anomaly_sd')
    op.add_column('users', sa.Column('contact', sa.String(length=30), nullable=False, server_default=''))
    op.alter_column('users', 'contact', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'contact')
    op.add_column('settings', sa.Column('anomaly_sd', sa.Float(), nullable=False, server_default='2.5'))
    op.alter_column('settings', 'anomaly_sd', server_default=None)
    op.drop_column('settings', 'anomaly_pct')
