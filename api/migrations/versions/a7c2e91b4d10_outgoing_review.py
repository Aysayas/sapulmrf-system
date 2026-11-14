"""outgoing review: operators' outgoing counts at once, the admin marks it ok or reverses it

Revision ID: a7c2e91b4d10
Revises: 83dfb59b4301
Create Date: 2026-11-14 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c2e91b4d10'
down_revision: Union[str, Sequence[str], None] = '83dfb59b4301'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('outgoing', sa.Column('review', sa.String(length=8), nullable=True))
    op.add_column('outgoing', sa.Column('reviewed_by', sa.Integer(), nullable=True))
    op.add_column('outgoing', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('outgoing_reviewed_by_fkey', 'outgoing', 'users', ['reviewed_by'], ['id'], ondelete='SET NULL')
    op.create_check_constraint('ck_outgoing_review', 'outgoing', "review IN ('ok', 'reversed')")
    # rows the admin already approved under the old flow were reviewed then
    op.execute("UPDATE outgoing SET review = 'ok', reviewed_by = decided_by, reviewed_at = decided_at "
               "WHERE status = 'approved'")


def downgrade() -> None:
    op.drop_constraint('ck_outgoing_review', 'outgoing', type_='check')
    op.drop_constraint('outgoing_reviewed_by_fkey', 'outgoing', type_='foreignkey')
    op.drop_column('outgoing', 'reviewed_at')
    op.drop_column('outgoing', 'reviewed_by')
    op.drop_column('outgoing', 'review')
