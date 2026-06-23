"""merge heads

Revision ID: 04bd8c2d6c8d
Revises: 816930c3f92d, a1b2c3d4e5f6
Create Date: 2026-06-16 17:01:26.200861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04bd8c2d6c8d'
down_revision: Union[str, None] = ('816930c3f92d', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
