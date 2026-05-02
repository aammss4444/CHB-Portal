"""add_dte_norm_columns

Revision ID: f9a1b2c3d4e5
Revises: e5f6a7b8c9d0
Create Date: 2026-04-28 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f9a1b2c3d4e5"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add institution_id FK column (needed for institution-scoped norm uniqueness)
    op.execute(
        "ALTER TABLE norms ADD COLUMN IF NOT EXISTS institution_id INTEGER "
        "REFERENCES institutions(id) ON DELETE CASCADE"
    )

    # Ensure norm_type has a default of 'GENERAL' (column already exists, just set default)
    op.execute("ALTER TABLE norms ALTER COLUMN norm_type SET DEFAULT 'GENERAL'")

    # Add course_category if not already present (idempotent)
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS course_category VARCHAR(100)")

    # Add grade_requirement with server_default (idempotent)
    op.execute(
        "ALTER TABLE norms ADD COLUMN IF NOT EXISTS grade_requirement VARCHAR(100) "
        "NOT NULL DEFAULT ''"
    )

    # Add min_qualification with server_default (idempotent)
    op.execute(
        "ALTER TABLE norms ADD COLUMN IF NOT EXISTS min_qualification VARCHAR(255) "
        "NOT NULL DEFAULT ''"
    )

    # Add max_age with default (idempotent)
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS max_age INTEGER DEFAULT 38")

    # Add workload_hours_per_week with default (idempotent)
    op.execute(
        "ALTER TABLE norms ADD COLUMN IF NOT EXISTS workload_hours_per_week INTEGER DEFAULT 18"
    )

    # Add practical_to_theory_ratio with default (idempotent)
    op.execute(
        "ALTER TABLE norms ADD COLUMN IF NOT EXISTS practical_to_theory_ratio FLOAT DEFAULT 0.5"
    )

    # Unique constraint: one norm per institution + year + type + category
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_norms_institution_year_type_category'
            ) THEN
                ALTER TABLE norms
                ADD CONSTRAINT uq_norms_institution_year_type_category
                UNIQUE (institution_id, academic_year, norm_type, course_category);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE norms DROP CONSTRAINT IF EXISTS uq_norms_institution_year_type_category"
    )
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS institution_id")
    op.execute("ALTER TABLE norms ALTER COLUMN norm_type DROP DEFAULT")
    # Note: grade_requirement, min_qualification, max_age, workload_hours_per_week,
    # practical_to_theory_ratio were added by d4e5f6a7b8c9 / e5f6a7b8c9d0 — do not drop here.
