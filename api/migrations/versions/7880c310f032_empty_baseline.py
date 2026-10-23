"""empty baseline

Revision ID: 7880c310f032
Revises: 
Create Date: 2026-10-23 03:00:29.206120

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '7880c310f032'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
