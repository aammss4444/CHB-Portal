"""add_slot_date_to_timetable

Revision ID: 819f4532846d
Revises: b54992442061
Create Date: 2026-06-29 15:54:04.114134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '819f4532846d'
down_revision: Union[str, None] = 'b54992442061'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add slot_date column
    op.add_column('timetable_slots', sa.Column('slot_date', sa.Date(), nullable=True))
    
    # Make day_of_week nullable (for backward compatibility during transition)
    op.alter_column('timetable_slots', 'day_of_week', nullable=True)
    
    # Drop old unique constraint
    op.drop_constraint('uq_timetable_faculty_slot_day_year', 'timetable_slots', type_='unique')
    
    # Create new unique constraint with slot_date
    op.create_unique_constraint(
        'uq_timetable_faculty_slot_date_time',
        'timetable_slots',
        ['institution_id', 'course_id', 'faculty_credential_id', 'slot_date', 'start_time', 'academic_year']
    )


def downgrade() -> None:
    # Drop new unique constraint
    op.drop_constraint('uq_timetable_faculty_slot_date_time', 'timetable_slots', type_='unique')
    
    # Recreate old unique constraint
    op.create_unique_constraint(
        'uq_timetable_faculty_slot_day_year',
        'timetable_slots',
        ['institution_id', 'course_id', 'faculty_credential_id', 'day_of_week', 'slot_number', 'academic_year']
    )
    
    # Make day_of_week not nullable again
    op.alter_column('timetable_slots', 'day_of_week', nullable=False)
    
    # Drop slot_date column
    op.drop_column('timetable_slots', 'slot_date')
