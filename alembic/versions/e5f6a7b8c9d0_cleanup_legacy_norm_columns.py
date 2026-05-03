"""cleanup_legacy_norm_columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-28 12:45:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill for stricter constraints.
    op.execute("UPDATE norms SET norm_type = 'GENERAL' WHERE norm_type IS NULL")

    # Remove legacy indexes if present.
    op.execute("DROP INDEX IF EXISTS ix_norms_course_level")
    op.execute("DROP INDEX IF EXISTS ix_norms_category")

    # Remove legacy columns no longer used by Step 1 norms.
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS course_level")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS category")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS max_daily_lectures")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS credit_to_hour_ratio")
    op.execute("ALTER TABLE norms DROP COLUMN IF EXISTS effective_date")

    # Enforce required columns.
    op.execute("ALTER TABLE norms ALTER COLUMN norm_type SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS course_level VARCHAR")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS category VARCHAR")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS max_daily_lectures INTEGER DEFAULT 6")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS credit_to_hour_ratio FLOAT DEFAULT 1.0")
    op.execute("ALTER TABLE norms ADD COLUMN IF NOT EXISTS effective_date TIMESTAMPTZ DEFAULT now()")
    op.execute("ALTER TABLE norms ALTER COLUMN norm_type DROP NOT NULL")
