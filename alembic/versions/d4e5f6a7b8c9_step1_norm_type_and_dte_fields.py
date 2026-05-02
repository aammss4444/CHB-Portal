"""step1_norm_type_and_dte_fields

Revision ID: d4e5f6a7b8c9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-28 12:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safe idempotent adds to support environments that already received hotfix SQL.
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS norm_type VARCHAR")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS course_category VARCHAR")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS grade_requirement VARCHAR")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS max_age INTEGER DEFAULT 38")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS workload_hours_per_week INTEGER DEFAULT 18")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS practical_to_theory_ratio FLOAT DEFAULT 0.5")

    # Performance indexes for norm resolution path.
    op.execute("CREATE INDEX IF NOT EXISTS ix_norms_norm_type ON norms (norm_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_norms_course_category ON norms (course_category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_norms_academic_year ON norms (academic_year)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_norms_resolution_lookup "
        "ON norms (norm_type, course_category, academic_year, category, id DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_norms_resolution_lookup")
    op.execute("DROP INDEX IF EXISTS ix_norms_academic_year")
    op.execute("DROP INDEX IF EXISTS ix_norms_course_category")
    op.execute("DROP INDEX IF EXISTS ix_norms_norm_type")

    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS practical_to_theory_ratio")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS workload_hours_per_week")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS max_age")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS grade_requirement")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS course_category")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS norm_type")
