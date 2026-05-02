"""step9_payment_disbursement

Revision ID: b3c4d5e6f7a8
Revises: a9b8c7d6e5f4
Create Date: 2026-04-24 00:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


payment_status_enum = postgresql.ENUM(
    "INITIATED",
    "PROCESSING",
    "SUCCESS",
    "FAILED",
    name="payment_status_enum",
    create_type=False,
)

payment_mode_enum = postgresql.ENUM(
    "BANK_TRANSFER",
    "UPI",
    "MANUAL",
    name="payment_mode_enum",
    create_type=False,
)


def upgrade() -> None:
    op.execute("ALTER TYPE bill_audit_action_enum ADD VALUE IF NOT EXISTS 'PAYMENT_INITIATED'")
    op.execute("ALTER TYPE bill_audit_action_enum ADD VALUE IF NOT EXISTS 'PAYMENT_SUCCESS'")
    op.execute("ALTER TYPE bill_audit_action_enum ADD VALUE IF NOT EXISTS 'PAYMENT_FAILED'")

    payment_status_enum.create(op.get_bind(), checkfirst=True)
    payment_mode_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payment_transaction",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_status", payment_status_enum, nullable=False, server_default="INITIATED"),
        sa.Column("payment_mode", payment_mode_enum, nullable=False, server_default="BANK_TRANSFER"),
        sa.Column("transaction_reference", sa.String(length=255), nullable=True),
        sa.Column("bank_reference", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bill_id"], ["chb_bill.id"]),
        sa.ForeignKeyConstraint(["faculty_credential_id"], ["faculty_credentials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_id", name="uq_payment_transaction_bill_id"),
    )
    op.create_index("ix_payment_transaction_payment_status", "payment_transaction", ["payment_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_transaction_payment_status", table_name="payment_transaction")
    op.drop_table("payment_transaction")
    payment_mode_enum.drop(op.get_bind(), checkfirst=True)
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
