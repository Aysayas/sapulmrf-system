"""lowercase usernames

Revision ID: d3fc67fd1d3e
Revises: a66767d19e26
Create Date: 2026-10-23 04:27:01.694618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3fc67fd1d3e'
down_revision: Union[str, Sequence[str], None] = 'a66767d19e26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Usernames are lowercase from now on; login lowercases what people type, so nobody's login changes."""
    op.execute("UPDATE users SET username = lower(username) WHERE username <> lower(username)")


def downgrade() -> None:
    """Nothing to undo: the original capitals aren't kept."""
