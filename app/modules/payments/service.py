from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill_audit import BillAudit, BillAuditAction
from app.models.chb_bill import BillStatus, CHBBill
from app.models.faculty_credentials import FacultyCredentials
from app.models.payment_transaction import PaymentMode, PaymentStatus, PaymentTransaction
from app.models.user import RoleEnum, User


class PaymentService:
    """Payment disbursement service for Step 9 with idempotent and auditable transitions."""

    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _enum_value(value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    async def _write_bill_audit(
        self,
        db: AsyncSession,
        bill_id: UUID,
        action: BillAuditAction,
        performed_by: Optional[int],
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> None:
        db.add(
            BillAudit(
                bill_id=bill_id,
                action=action.value,
                performed_by=performed_by,
                old_status=old_status,
                new_status=new_status,
                remarks=remarks,
            )
        )

    async def initiate_payment(
        self,
        bill_id: UUID,
        initiated_by: int,
        db: AsyncSession,
        payment_mode: str = PaymentMode.BANK_TRANSFER.value,
    ) -> PaymentTransaction:
        """Create an INITIATED payment transaction for an eligible treasury-processed bill."""
        bill = (
            await db.execute(
                select(CHBBill).where(CHBBill.id == bill_id).with_for_update()
            )
        ).scalars().first()
        if not bill:
            self._raise_error(404, "BILL_NOT_ELIGIBLE_FOR_PAYMENT", "Bill not found or not eligible for payment")

        if self._enum_value(bill.bill_status) != BillStatus.TREASURY_PROCESSED.value or not bill.is_locked:
            self._raise_error(
                400,
                "BILL_NOT_ELIGIBLE_FOR_PAYMENT",
                "Only TREASURY_PROCESSED and locked bills are eligible for payment",
            )

        existing = (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.bill_id == bill_id).with_for_update()
            )
        ).scalars().first()
        if existing and self._enum_value(existing.payment_status) == PaymentStatus.SUCCESS.value:
            self._raise_error(409, "PAYMENT_ALREADY_PROCESSED", "Payment already processed successfully for this bill")
        if existing and self._enum_value(existing.payment_status) in {
            PaymentStatus.INITIATED.value,
            PaymentStatus.PROCESSING.value,
        }:
            return existing
        if existing and self._enum_value(existing.payment_status) == PaymentStatus.FAILED.value:
            self._raise_error(400, "INVALID_PAYMENT_STATE", "Payment is FAILED. Use retry endpoint.")

        try:
            resolved_mode = PaymentMode(payment_mode).value
        except ValueError:
            self._raise_error(400, "INVALID_PAYMENT_STATE", f"Unsupported payment mode: {payment_mode}")

        transaction = PaymentTransaction(
            bill_id=bill.id,
            faculty_credential_id=bill.faculty_credential_id,
            amount=Decimal(bill.net_amount),
            payment_status=PaymentStatus.INITIATED.value,
            payment_mode=resolved_mode,
            initiated_at=datetime.utcnow(),
        )
        db.add(transaction)
        await db.flush()

        await self._write_bill_audit(
            db=db,
            bill_id=bill.id,
            action=BillAuditAction.PAYMENT_INITIATED,
            performed_by=initiated_by,
            old_status=PaymentStatus.INITIATED.value,
            new_status=PaymentStatus.INITIATED.value,
            remarks=f"payment_id={transaction.id}",
        )
        await db.commit()
        await db.refresh(transaction)
        return transaction

    async def process_payment(
        self,
        payment_id: UUID,
        db: AsyncSession,
        processed_by: Optional[int] = None,
        force_success: Optional[bool] = None,
    ) -> PaymentTransaction:
        """Process an INITIATED payment via simulated gateway and persist terminal status."""
        payment = (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.id == payment_id).with_for_update()
            )
        ).scalars().first()
        if not payment:
            self._raise_error(404, "PAYMENT_NOT_FOUND", "Payment transaction not found")

        current_status = self._enum_value(payment.payment_status)
        if current_status == PaymentStatus.SUCCESS.value:
            self._raise_error(409, "PAYMENT_ALREADY_SUCCESS", "Payment is already in SUCCESS state")
        if current_status not in {PaymentStatus.INITIATED.value, PaymentStatus.FAILED.value}:
            self._raise_error(400, "INVALID_PAYMENT_STATE", f"Cannot process payment from state {current_status}")

        payment.payment_status = PaymentStatus.PROCESSING.value
        await db.flush()

        is_success = force_success if force_success is not None else random.choice([True, False])
        if is_success:
            payment.payment_status = PaymentStatus.SUCCESS.value
            payment.failure_reason = None
            payment.processed_at = datetime.utcnow()
            payment.transaction_reference = f"TXN-{payment.id.hex[:12].upper()}"
            payment.bank_reference = f"BANK-{payment.id.hex[12:24].upper()}"
            await self._write_bill_audit(
                db=db,
                bill_id=payment.bill_id,
                action=BillAuditAction.PAYMENT_SUCCESS,
                performed_by=processed_by,
                old_status=PaymentStatus.PROCESSING.value,
                new_status=PaymentStatus.SUCCESS.value,
                remarks=f"transaction_reference={payment.transaction_reference}",
            )
        else:
            payment.payment_status = PaymentStatus.FAILED.value
            payment.processed_at = datetime.utcnow()
            payment.failure_reason = payment.failure_reason or "Simulated payment gateway failure"
            payment.transaction_reference = None
            payment.bank_reference = None
            await self._write_bill_audit(
                db=db,
                bill_id=payment.bill_id,
                action=BillAuditAction.PAYMENT_FAILED,
                performed_by=processed_by,
                old_status=PaymentStatus.PROCESSING.value,
                new_status=PaymentStatus.FAILED.value,
                remarks=payment.failure_reason,
            )

        await db.commit()
        await db.refresh(payment)
        return payment

    async def retry_payment(
        self,
        payment_id: UUID,
        db: AsyncSession,
        retried_by: Optional[int] = None,
        force_success: Optional[bool] = None,
    ) -> PaymentTransaction:
        """Retry only FAILED payments and process simulated gateway outcome atomically."""
        payment = (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.id == payment_id).with_for_update()
            )
        ).scalars().first()
        if not payment:
            self._raise_error(404, "PAYMENT_NOT_FOUND", "Payment transaction not found")

        if self._enum_value(payment.payment_status) != PaymentStatus.FAILED.value:
            self._raise_error(400, "INVALID_PAYMENT_STATE", "Retry is allowed only for FAILED payments")

        payment.payment_status = PaymentStatus.INITIATED.value
        payment.failure_reason = None
        payment.processed_at = None
        payment.transaction_reference = None
        payment.bank_reference = None
        await db.flush()

        await self._write_bill_audit(
            db=db,
            bill_id=payment.bill_id,
            action=BillAuditAction.PAYMENT_INITIATED,
            performed_by=retried_by,
            old_status=PaymentStatus.FAILED.value,
            new_status=PaymentStatus.INITIATED.value,
            remarks=f"retry_payment_id={payment.id}",
        )

        payment.payment_status = PaymentStatus.PROCESSING.value
        await db.flush()

        is_success = force_success if force_success is not None else random.choice([True, False])
        if is_success:
            payment.payment_status = PaymentStatus.SUCCESS.value
            payment.failure_reason = None
            payment.processed_at = datetime.utcnow()
            payment.transaction_reference = f"TXN-{payment.id.hex[:12].upper()}"
            payment.bank_reference = f"BANK-{payment.id.hex[12:24].upper()}"
            await self._write_bill_audit(
                db=db,
                bill_id=payment.bill_id,
                action=BillAuditAction.PAYMENT_SUCCESS,
                performed_by=retried_by,
                old_status=PaymentStatus.PROCESSING.value,
                new_status=PaymentStatus.SUCCESS.value,
                remarks=f"transaction_reference={payment.transaction_reference}",
            )
        else:
            payment.payment_status = PaymentStatus.FAILED.value
            payment.processed_at = datetime.utcnow()
            payment.failure_reason = "Simulated payment gateway failure"
            payment.transaction_reference = None
            payment.bank_reference = None
            await self._write_bill_audit(
                db=db,
                bill_id=payment.bill_id,
                action=BillAuditAction.PAYMENT_FAILED,
                performed_by=retried_by,
                old_status=PaymentStatus.PROCESSING.value,
                new_status=PaymentStatus.FAILED.value,
                remarks=payment.failure_reason,
            )

        await db.commit()
        await db.refresh(payment)
        return payment

    async def get_payment(self, payment_id: UUID, current_user: User, db: AsyncSession) -> PaymentTransaction:
        """Fetch one payment transaction with FACULTY ownership enforcement."""
        payment = (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
            )
        ).scalars().first()
        if not payment:
            self._raise_error(404, "PAYMENT_NOT_FOUND", "Payment transaction not found")

        if current_user.role == RoleEnum.FACULTY:
            own_credential = (
                await db.execute(
                    select(FacultyCredentials.id).where(FacultyCredentials.user_id == current_user.id)
                )
            ).scalar_one_or_none()
            if own_credential != payment.faculty_credential_id:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "Faculty can only view own payment records")
        return payment

    async def list_payments(
        self,
        db: AsyncSession,
        institution_id: Optional[int],
        status: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[PaymentTransaction], int]:
        """List payments with explicit joins and filter support."""
        stmt = (
            select(PaymentTransaction)
            .join(CHBBill, CHBBill.id == PaymentTransaction.bill_id)
        )
        filters = []
        if institution_id is not None:
            filters.append(CHBBill.institution_id == institution_id)
        if status:
            filters.append(PaymentTransaction.payment_status == status)
        if start_date is not None:
            filters.append(PaymentTransaction.created_at >= start_date)
        if end_date is not None:
            filters.append(PaymentTransaction.created_at <= end_date)
        if filters:
            stmt = stmt.where(and_(*filters))
            
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(PaymentTransaction.created_at.desc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)
            
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total
