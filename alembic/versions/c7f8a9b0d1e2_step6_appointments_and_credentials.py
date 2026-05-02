"""step6_appointments_and_credentials

Revision ID: c7f8a9b0d1e2
Revises: b1c2d3e4f5a6
Create Date: 2026-04-23 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7f8a9b0d1e2"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_enum e ON t.oid = e.enumtypid
                    WHERE t.typname = 'roleenum' AND e.enumlabel = 'FACULTY'
                ) THEN
                    ALTER TYPE roleenum ADD VALUE 'FACULTY';
                END IF;
            END $$;
            """
        )

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN DEFAULT FALSE NOT NULL")

    op.create_table(
        "appointment_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "appointment_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_number", sa.String(length=50), nullable=False),
        sa.Column("selection_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("designation", sa.String(length=100), nullable=False),
        sa.Column("joining_date", sa.Date(), nullable=False),
        sa.Column("salary_per_lecture", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("content_en", sa.Text(), nullable=False),
        sa.Column("content_mr", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.Integer(), nullable=True),
        sa.Column("acceptance_deadline", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["selection_result_id"], ["selection_results.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_number"),
        sa.UniqueConstraint("selection_result_id", name="_appointment_selection_result_uc"),
    )

    op.create_table(
        "appointment_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_letter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("actioned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["appointment_letter_id"], ["appointment_letters.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "faculty_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_letter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("faculty_code", sa.String(length=50), nullable=False),
        sa.Column("portal_username", sa.String(length=100), nullable=False),
        sa.Column("temp_password_hash", sa.String(), nullable=False),
        sa.Column("credential_issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("first_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["appointment_letter_id"], ["appointment_letters.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_letter_id"),
        sa.UniqueConstraint("faculty_code"),
        sa.UniqueConstraint("portal_username"),
    )

    op.create_table(
        "appointment_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_letter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["appointment_letter_id"], ["appointment_letters.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("appointment_audit")
    op.drop_table("faculty_credentials")
    op.drop_table("appointment_acceptances")
    op.drop_table("appointment_letters")
    op.drop_table("appointment_templates")

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS force_password_change")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active")
