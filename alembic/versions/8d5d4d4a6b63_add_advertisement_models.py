"""add_advertisement_models

Revision ID: 8d5d4d4a6b63
Revises: 645eefca145f
Create Date: 2026-04-22 22:46:20.736784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d5d4d4a6b63"
down_revision: Union[str, None] = "645eefca145f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("institution_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_institution_id_institutions",
        "users",
        "institutions",
        ["institution_id"],
        ["id"],
    )

    op.create_table(
        "advertisement_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "advertisements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("vacancy_count", sa.Integer(), nullable=False),
        sa.Column("content_en", sa.Text(), nullable=False),
        sa.Column("content_mr", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True, server_default="DRAFT"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_start_date", sa.Date(), nullable=True),
        sa.Column("application_end_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["assessment_id"], ["vacancy_assessments.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "course_id", "academic_year", name="_adv_inst_branch_year_uc"),
    )

    op.create_table(
        "advertisement_audit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advertisement_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["advertisement_id"], ["advertisements.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "published_advertisements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advertisement_id", sa.UUID(), nullable=False),
        sa.Column("public_token", sa.String(length=100), nullable=False),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["advertisement_id"], ["advertisements.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("advertisement_id"),
        sa.UniqueConstraint("public_token"),
    )


def downgrade() -> None:
    op.drop_table("published_advertisements")
    op.drop_table("advertisement_audit")
    op.drop_table("advertisements")
    op.drop_table("advertisement_templates")

    op.drop_constraint("fk_users_institution_id_institutions", "users", type_="foreignkey")
    op.drop_column("users", "institution_id")
