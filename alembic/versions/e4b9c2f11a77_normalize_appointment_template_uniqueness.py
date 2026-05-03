"""normalize appointment template uniqueness by name+language

Revision ID: e4b9c2f11a77
Revises: c7f8a9b0d1e2
Create Date: 2026-04-23 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e4b9c2f11a77"
down_revision: Union[str, None] = "c7f8a9b0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'appointment_templates_name_key'
            ) THEN
                ALTER TABLE appointment_templates DROP CONSTRAINT appointment_templates_name_key;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        UPDATE appointment_templates t
        SET name = 'CHB_APPOINTMENT_V1'
        WHERE t.name IN ('CHB_APPOINTMENT_V1_EN', 'CHB_APPOINTMENT_V1_MR')
          AND NOT EXISTS (
              SELECT 1
              FROM appointment_templates x
              WHERE x.name = 'CHB_APPOINTMENT_V1'
                AND x.language = t.language
          );
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_appointment_template_name_language'
            ) THEN
                ALTER TABLE appointment_templates
                ADD CONSTRAINT uq_appointment_template_name_language UNIQUE (name, language);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_appointment_template_name_language'
            ) THEN
                ALTER TABLE appointment_templates DROP CONSTRAINT uq_appointment_template_name_language;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'appointment_templates_name_key'
            ) THEN
                ALTER TABLE appointment_templates ADD CONSTRAINT appointment_templates_name_key UNIQUE (name);
            END IF;
        END $$;
        """
    )
