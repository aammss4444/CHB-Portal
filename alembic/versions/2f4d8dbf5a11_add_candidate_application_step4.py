"""add_candidate_application_step4

Revision ID: 2f4d8dbf5a11
Revises: 8d5d4d4a6b63
Create Date: 2026-04-23 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2f4d8dbf5a11"
down_revision: Union[str, None] = "8d5d4d4a6b63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("father_name", sa.String(length=255), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("religion", sa.String(length=50), nullable=True),
        sa.Column("nationality", sa.String(length=50), nullable=False, server_default="Indian"),
        sa.Column("mobile", sa.String(length=15), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=10), nullable=True),
        sa.Column("aadhar_number", sa.String(length=128), nullable=True),
        sa.Column("is_profile_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("aadhar_number"),
    )

    op.create_table(
        "candidate_qualifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("degree", sa.String(length=100), nullable=False),
        sa.Column("specialization", sa.String(length=100), nullable=True),
        sa.Column("university", sa.String(length=255), nullable=True),
        sa.Column("year_of_passing", sa.Integer(), nullable=True),
        sa.Column("percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("is_highest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "candidate_experience",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("institution_name", sa.String(length=255), nullable=True),
        sa.Column("designation", sa.String(length=100), nullable=True),
        sa.Column("from_date", sa.Date(), nullable=True),
        sa.Column("to_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("experience_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advertisement_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("application_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("applied_designation", sa.String(length=100), nullable=True),
        sa.Column("declaration_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["advertisement_id"], ["advertisements.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_number"),
        sa.UniqueConstraint("advertisement_id", "candidate_id", name="_app_ad_candidate_uc"),
    )

    op.create_table(
        "application_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size_kb", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "document_validation_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("check_type", sa.String(length=100), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["application_documents.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("document_validation_log")
    op.drop_table("application_documents")
    op.drop_table("applications")
    op.drop_table("candidate_experience")
    op.drop_table("candidate_qualifications")
    op.drop_table("candidates")
