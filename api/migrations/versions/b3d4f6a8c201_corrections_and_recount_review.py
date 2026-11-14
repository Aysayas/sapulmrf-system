"""corrections (undo with a reason) and recount review: recounts count at once, the admin marks ok or reverses

Revision ID: b3d4f6a8c201
Revises: a7c2e91b4d10
Create Date: 2026-11-14 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3d4f6a8c201'
down_revision: Union[str, Sequence[str], None] = 'a7c2e91b4d10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'corrections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('record_code', sa.String(length=12), nullable=False),
        sa.Column('summary', sa.String(length=300), nullable=False),
        sa.Column('reason', sa.String(length=120), nullable=False),
        sa.Column('by', sa.Integer(), nullable=True),
        sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('redone_as', sa.String(length=12), nullable=True),
        sa.Column('review', sa.String(length=8), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('sort', 'segregation', 'delivery')", name='ck_corrections_kind'),
        sa.CheckConstraint("review IN ('ok', 'wrong')", name='ck_corrections_review'),
        sa.ForeignKeyConstraint(['by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_corrections_record_code', 'corrections', ['record_code'])
    op.create_index('ix_corrections_at', 'corrections', ['at'])

    op.add_column('adjustment_requests', sa.Column('review', sa.String(length=8), nullable=True))
    op.add_column('adjustment_requests', sa.Column('reviewed_by', sa.Integer(), nullable=True))
    op.add_column('adjustment_requests', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('adjustment_requests_reviewed_by_fkey', 'adjustment_requests', 'users', ['reviewed_by'], ['id'],
                          ondelete='SET NULL')
    op.create_check_constraint('ck_adjustment_review', 'adjustment_requests', "review IN ('ok', 'reversed')")
    # counts the admin already decided were looked at then
    op.execute("UPDATE adjustment_requests SET review = 'ok', reviewed_by = decided_by, reviewed_at = decided_at "
               "WHERE status = 'approved'")


def downgrade() -> None:
    op.drop_constraint('ck_adjustment_review', 'adjustment_requests', type_='check')
    op.drop_constraint('adjustment_requests_reviewed_by_fkey', 'adjustment_requests', type_='foreignkey')
    op.drop_column('adjustment_requests', 'reviewed_at')
    op.drop_column('adjustment_requests', 'reviewed_by')
    op.drop_column('adjustment_requests', 'review')
    op.drop_index('ix_corrections_at', table_name='corrections')
    op.drop_index('ix_corrections_record_code', table_name='corrections')
    op.drop_table('corrections')
