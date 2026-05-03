"""rename_branches_to_courses

Renames the `branches` table to `courses` and renames all `branch_id` FK
columns to `course_id` across every dependent table.
Also renames related unique constraints and sequences.

Revision ID: a1b2c3d4e5f6
Revises: f9a1b2c3d4e5
Create Date: 2026-04-29 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that have a branch_id column pointing to branches.id
_TABLES_WITH_BRANCH_FK = [
    "intake_definitions",
    "existing_faculty",
    "vacancy_assessments",
    "advertisements",
    "applications",
    "selection_rounds",
    "selection_results",
    "appointment_letters",
    "timetable_slots",
    "lecture_logs",
    "daily_attendance_summary",
    "chb_bill",
    "scoring_weight_configs",
]


def upgrade() -> None:
    # 1. Rename the table branches → courses
    op.execute("ALTER TABLE branches RENAME TO courses")

    # 2. Rename the primary key sequence if it exists
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'branches_id_seq') THEN "
        "    ALTER SEQUENCE branches_id_seq RENAME TO courses_id_seq; "
        "  END IF; "
        "END $$;"
    )

    # 3. Rename the primary key index if it exists
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_branches_id') THEN "
        "    ALTER INDEX ix_branches_id RENAME TO ix_courses_id; "
        "  END IF; "
        "END $$;"
    )

    # 4. Rename branch_id → course_id in every dependent table
    for table in _TABLES_WITH_BRANCH_FK:
        op.execute(
            f"ALTER TABLE {table} RENAME COLUMN branch_id TO course_id"
        )

    # 5. Rename unique constraints that referenced branch_id
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '_inst_branch_year_uc') THEN "
        "    ALTER TABLE vacancy_assessments "
        "      RENAME CONSTRAINT _inst_branch_year_uc TO _inst_course_year_uc; "
        "  END IF; "
        "END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '_adv_inst_branch_year_uc') THEN "
        "    ALTER TABLE advertisements "
        "      RENAME CONSTRAINT _adv_inst_branch_year_uc TO _adv_inst_course_year_uc; "
        "  END IF; "
        "END $$;"
    )

    # 6. Rename the FK constraint on the courses table itself
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'branches_institution_id_fkey') THEN "
        "    ALTER TABLE courses "
        "      RENAME CONSTRAINT branches_institution_id_fkey TO courses_institution_id_fkey; "
        "  END IF; "
        "END $$;"
    )


def downgrade() -> None:
    # Reverse FK constraint rename on courses table
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'courses_institution_id_fkey') THEN "
        "    ALTER TABLE courses "
        "      RENAME CONSTRAINT courses_institution_id_fkey TO branches_institution_id_fkey; "
        "  END IF; "
        "END $$;"
    )

    # Reverse unique constraint renames
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '_inst_course_year_uc') THEN "
        "    ALTER TABLE vacancy_assessments "
        "      RENAME CONSTRAINT _inst_course_year_uc TO _inst_branch_year_uc; "
        "  END IF; "
        "END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '_adv_inst_course_year_uc') THEN "
        "    ALTER TABLE advertisements "
        "      RENAME CONSTRAINT _adv_inst_course_year_uc TO _adv_inst_branch_year_uc; "
        "  END IF; "
        "END $$;"
    )

    # Reverse column renames: course_id → branch_id
    for table in _TABLES_WITH_BRANCH_FK:
        op.execute(
            f"ALTER TABLE {table} RENAME COLUMN course_id TO branch_id"
        )

    # Reverse sequence rename
    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'courses_id_seq') THEN "
        "    ALTER SEQUENCE courses_id_seq RENAME TO branches_id_seq; "
        "  END IF; "
        "END $$;"
    )

    # Reverse table rename: courses → branches
    op.execute("ALTER TABLE courses RENAME TO branches")
