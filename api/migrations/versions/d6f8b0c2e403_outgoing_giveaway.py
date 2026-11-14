"""outgoing giveaway: recyclables given away free (no price), reported apart from sales

Revision ID: d6f8b0c2e403
Revises: c5e7a9b1d302
Create Date: 2026-11-15 12:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd6f8b0c2e403'
down_revision: Union[str, Sequence[str], None] = 'c5e7a9b1d302'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_outgoing_type', 'outgoing', type_='check')
    op.create_check_constraint('ck_outgoing_type', 'outgoing', "type IN ('sale', 'compost', 'disposal', 'giveaway')")


def downgrade() -> None:
    op.execute("DELETE FROM outgoing WHERE type = 'giveaway'")  # the old rule can't hold them
    op.drop_constraint('ck_outgoing_type', 'outgoing', type_='check')
    op.create_check_constraint('ck_outgoing_type', 'outgoing', "type IN ('sale', 'compost', 'disposal')")
