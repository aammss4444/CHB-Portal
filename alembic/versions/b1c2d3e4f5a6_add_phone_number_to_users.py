"""add_phone_number_to_users

Revision ID: b1c2d3e4f5a6
Revises: 91eaa9285cf0
Create Date: 2026-04-23 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "91eaa9285cf0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS phone_number")
