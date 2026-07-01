"""make_slot_date_not_null

Revision ID: aebd3f748181
Revises: 819f4532846d
Create Date: 2026-06-29 16:00:53.270546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aebd3f748181'
down_revision: Union[str, None] = '819f4532846d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete any slots without slot_date (cleanup old data)
    op.execute("DELETE FROM timetable_slots WHERE slot_date IS NULL")
    
    # Make slot_date NOT NULL
    op.alter_column('timetable_slots', 'slot_date', nullable=False)


def downgrade() -> None:
    # Make slot_date nullable again
    op.alter_column('timetable_slots', 'slot_date', nullable=True)
