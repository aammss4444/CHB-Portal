"""Change timetable calendar_date to day_of_week

Revision ID: b54992442061
Revises: 04bd8c2d6c8d
Create Date: 2026-06-29 15:27:53.524187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b54992442061'
down_revision: Union[str, None] = '04bd8c2d6c8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_timetable_faculty_slot_date_year', 'timetable_slots', type_='unique')
    op.drop_column('timetable_slots', 'calendar_date')
    op.add_column('timetable_slots', sa.Column('day_of_week', sa.String(length=10), nullable=False, server_default='MONDAY'))
    op.alter_column('timetable_slots', 'day_of_week', server_default=None)
    op.create_unique_constraint('uq_timetable_faculty_slot_day_year', 'timetable_slots', ['institution_id', 'course_id', 'faculty_credential_id', 'day_of_week', 'slot_number', 'academic_year'])


def downgrade() -> None:
    op.drop_constraint('uq_timetable_faculty_slot_day_year', 'timetable_slots', type_='unique')
    op.drop_column('timetable_slots', 'day_of_week')
    op.add_column('timetable_slots', sa.Column('calendar_date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')))
    op.alter_column('timetable_slots', 'calendar_date', server_default=None)
    op.create_unique_constraint('uq_timetable_faculty_slot_date_year', 'timetable_slots', ['institution_id', 'course_id', 'faculty_credential_id', 'calendar_date', 'slot_number', 'academic_year'])
