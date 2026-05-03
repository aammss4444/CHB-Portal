"""step8_bill_generation

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-04-23 23:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


chb_designation_enum = postgresql.ENUM(
    "ASSISTANT_PROFESSOR",
    "ASSOCIATE_PROFESSOR",
    "PROFESSOR",
    "VISITING_FACULTY",
    "GUEST_FACULTY",
    name="chb_designation_enum",
    create_type=False,
)
rate_lecture_type_enum = postgresql.ENUM(
    "THEORY",
    "LAB",
    "TUTORIAL",
    name="rate_lecture_type_enum",
    create_type=False,
)
chb_bill_status_enum = postgresql.ENUM(
    "DRAFT",
    "SUBMITTED",
    "PRINCIPAL_APPROVED",
    "RO_APPROVED",
    "DIRECTORATE_APPROVED",
    "TREASURY_PROCESSED",
    "REJECTED",
    name="chb_bill_status_enum",
    create_type=False,
)
chb_bill_approver_role_enum = postgresql.ENUM(
    "PRINCIPAL",
    "RO",
    "DIRECTORATE",
    "TREASURY",
    name="chb_bill_approver_role_enum",
    create_type=False,
)
bill_line_lecture_type_enum = postgresql.ENUM(
    "THEORY",
    "LAB",
    "TUTORIAL",
    "EXTRA",
    "SUBSTITUTE",
    name="bill_line_lecture_type_enum",
    create_type=False,
)
bill_approval_action_enum = postgresql.ENUM(
    "APPROVED",
    "REJECTED",
    "SENT_BACK",
    name="bill_approval_action_enum",
    create_type=False,
)
bill_audit_action_enum = postgresql.ENUM(
    "CREATED",
    "SUBMITTED",
    "APPROVED",
    "REJECTED",
    "SENT_BACK",
    "TREASURY_PROCESSED",
    "REGENERATED",
    name="bill_audit_action_enum",
    create_type=False,
)


def upgrade() -> None:
    chb_designation_enum.create(op.get_bind(), checkfirst=True)
    rate_lecture_type_enum.create(op.get_bind(), checkfirst=True)
    chb_bill_status_enum.create(op.get_bind(), checkfirst=True)
    chb_bill_approver_role_enum.create(op.get_bind(), checkfirst=True)
    bill_line_lecture_type_enum.create(op.get_bind(), checkfirst=True)
    bill_approval_action_enum.create(op.get_bind(), checkfirst=True)
    bill_audit_action_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "rate_master",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("designation", chb_designation_enum, nullable=False),
        sa.Column("lecture_type", rate_lecture_type_enum, nullable=False),
        sa.Column("rate_per_lecture", sa.Numeric(10, 2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "institution_id",
            "academic_year",
            "designation",
            "lecture_type",
            "effective_from",
            name="uq_rate_master_institution_year_designation_type_effective_from",
        ),
    )

    op.create_table(
        "chb_bill",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_number", sa.String(length=50), nullable=False),
        sa.Column("faculty_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("designation", sa.String(length=100), nullable=False),
        sa.Column("total_theory_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lab_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tutorial_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_extra_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_substitute_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_billable_lectures", sa.Integer(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("deductions", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("bill_status", chb_bill_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("current_approver_role", chb_bill_approver_role_enum, nullable=True),
        sa.Column("rejection_stage", sa.String(length=50), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("generated_by", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("treasury_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["faculty_credential_id"], ["faculty_credentials.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_number", name="uq_chb_bill_bill_number"),
        sa.UniqueConstraint("faculty_credential_id", "period_start", "period_end", name="uq_chb_bill_faculty_period"),
    )

    op.create_table(
        "bill_line_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lecture_log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lecture_date", sa.Date(), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=False),
        sa.Column("lecture_type", bill_line_lecture_type_enum, nullable=False),
        sa.Column("class_name", sa.String(length=100), nullable=True),
        sa.Column("rate_per_lecture", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_extra", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_substitute", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bill_id"], ["chb_bill.id"]),
        sa.ForeignKeyConstraint(["lecture_log_id"], ["lecture_logs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bill_approval",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_role", chb_bill_approver_role_enum, nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=False),
        sa.Column("action", bill_approval_action_enum, nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bill_id"], ["chb_bill.id"]),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bill_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", bill_audit_action_enum, nullable=False),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("old_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bill_id"], ["chb_bill.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        "ALTER TABLE daily_attendance_summary ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE daily_attendance_summary ADD COLUMN IF NOT EXISTS lock_reason VARCHAR(100)"
    )


def downgrade() -> None:
    op.drop_table("bill_audit")
    op.drop_table("bill_approval")
    op.drop_table("bill_line_item")
    op.drop_table("chb_bill")
    op.drop_table("rate_master")

    bill_audit_action_enum.drop(op.get_bind(), checkfirst=True)
    bill_approval_action_enum.drop(op.get_bind(), checkfirst=True)
    bill_line_lecture_type_enum.drop(op.get_bind(), checkfirst=True)
    chb_bill_approver_role_enum.drop(op.get_bind(), checkfirst=True)
    chb_bill_status_enum.drop(op.get_bind(), checkfirst=True)
    rate_lecture_type_enum.drop(op.get_bind(), checkfirst=True)
    chb_designation_enum.drop(op.get_bind(), checkfirst=True)
