"""buyers: regular buyers and recipients the kiosk shows as buttons (seeded from recent outgoing)

Revision ID: c5e7a9b1d302
Revises: b3d4f6a8c201
Create Date: 2026-11-15 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5e7a9b1d302'
down_revision: Union[str, Sequence[str], None] = 'b3d4f6a8c201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'buyers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    # start with the names already used, newest first, so the kiosk has buttons on day one
    op.execute("""
        INSERT INTO buyers (name, active)
        SELECT name, true FROM (
            SELECT left(trim(recipient), 80) AS name, max(id) AS last FROM outgoing
            WHERE trim(recipient) <> '' GROUP BY left(trim(recipient), 80)
            ORDER BY last DESC LIMIT 10
        ) recent
    """)


def downgrade() -> None:
    op.drop_table('buyers')
