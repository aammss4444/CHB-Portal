"""step7_attendance_work_log

Revision ID: f1a2b3c4d5e6
Revises: e4b9c2f11a77
Create Date: 2026-04-23 21:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e4b9c2f11a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


weekday_enum = postgresql.ENUM(
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    name="attendance_weekday_enum",
    create_type=False,
)
calendar_day_type_enum = postgresql.ENUM(
    "WORKING",
    "HOLIDAY",
    "EXAM",
    "HALF_DAY",
    "COMPENSATORY",
    name="calendar_day_type_enum",
    create_type=False,
)
timetable_lecture_type_enum = postgresql.ENUM(
    "THEORY",
    "LAB",
    "TUTORIAL",
    name="timetable_lecture_type_enum",
    create_type=False,
)
lecture_log_type_enum = postgresql.ENUM(
    "THEORY",
    "LAB",
    "TUTORIAL",
    "SUBSTITUTE",
    "EXTRA",
    name="lecture_log_type_enum",
    create_type=False,
)
lecture_log_status_enum = postgresql.ENUM(
    "DRAFT",
    "SUBMITTED",
    "VERIFIED",
    "REJECTED",
    "FLAGGED",
    name="lecture_log_status_enum",
    create_type=False,
)
anomaly_severity_enum = postgresql.ENUM(
    "LOW",
    "MEDIUM",
    "HIGH",
    name="anomaly_severity_enum",
    create_type=False,
)
lecture_log_audit_action_enum = postgresql.ENUM(
    "CREATED",
    "EDITED",
    "SUBMITTED",
    "VERIFIED",
    "REJECTED",
    "FLAGGED",
    "ANOMALY_DETECTED",
    name="lecture_log_audit_action_enum",
    create_type=False,
)


def upgrade() -> None:
    weekday_enum.create(op.get_bind(), checkfirst=True)
    calendar_day_type_enum.create(op.get_bind(), checkfirst=True)
    timetable_lecture_type_enum.create(op.get_bind(), checkfirst=True)
    lecture_log_type_enum.create(op.get_bind(), checkfirst=True)
    lecture_log_status_enum.create(op.get_bind(), checkfirst=True)
    anomaly_severity_enum.create(op.get_bind(), checkfirst=True)
    lecture_log_audit_action_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "timetable_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("faculty_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("day_of_week", weekday_enum, nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=False),
        sa.Column("lecture_type", timetable_lecture_type_enum, nullable=False),
        sa.Column("class_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["faculty_credential_id"], ["faculty_credentials.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "institution_id",
            "course_id",
            "faculty_credential_id",
            "day_of_week",
            "slot_number",
            "academic_year",
            name="uq_timetable_faculty_slot_day_year",
        ),
    )

    op.create_table(
        "lecture_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timetable_slot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("lecture_date", sa.Date(), nullable=False),
        sa.Column("day_of_week", weekday_enum, nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=False),
        sa.Column("lecture_type", lecture_log_type_enum, nullable=False),
        sa.Column("class_name", sa.String(length=100), nullable=True),
        sa.Column("topic_covered", sa.Text(), nullable=False),
        sa.Column("attendance_count", sa.Integer(), nullable=True),
        sa.Column("is_extra", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_substitute", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("substitute_for_faculty_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("log_status", lecture_log_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["faculty_credential_id"], ["faculty_credentials.id"]),
        sa.ForeignKeyConstraint(["timetable_slot_id"], ["timetable_slots.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["substitute_for_faculty_id"], ["faculty_credentials.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("faculty_credential_id", "lecture_date", "slot_number", name="uq_lecture_log_faculty_date_slot"),
    )

    op.create_table(
        "daily_attendance_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("scheduled_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conducted_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("substitute_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_billable_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_present", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_holiday", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lock_reason", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["faculty_credential_id"], ["faculty_credentials.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("faculty_credential_id", "attendance_date", name="uq_daily_attendance_faculty_date"),
    )

    op.create_table(
        "attendance_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lecture_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("anomaly_type", sa.String(length=100), nullable=False),
        sa.Column("severity", anomaly_severity_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_by", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledgement_remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["faculty_credential_id"], ["faculty_credentials.id"]),
        sa.ForeignKeyConstraint(["lecture_log_id"], ["lecture_logs.id"]),
        sa.ForeignKeyConstraint(["summary_id"], ["daily_attendance_summary.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "academic_calendar",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column("day_type", calendar_day_type_enum, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "calendar_date", "academic_year", name="uq_calendar_date_institution_year"),
    )

    op.create_table(
        "lecture_log_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lecture_log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", lecture_log_audit_action_enum, nullable=False),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lecture_log_id"], ["lecture_logs.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("lecture_log_audit")
    op.drop_table("academic_calendar")
    op.drop_table("attendance_anomalies")
    op.drop_table("daily_attendance_summary")
    op.drop_table("lecture_logs")
    op.drop_table("timetable_slots")

    lecture_log_audit_action_enum.drop(op.get_bind(), checkfirst=True)
    anomaly_severity_enum.drop(op.get_bind(), checkfirst=True)
    lecture_log_status_enum.drop(op.get_bind(), checkfirst=True)
    lecture_log_type_enum.drop(op.get_bind(), checkfirst=True)
    timetable_lecture_type_enum.drop(op.get_bind(), checkfirst=True)
    calendar_day_type_enum.drop(op.get_bind(), checkfirst=True)
    weekday_enum.drop(op.get_bind(), checkfirst=True)
