from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.payments.schemas import PaymentInitiateRequest, PaymentProcessRequest, PaymentRetryRequest
from app.modules.payments.service import PaymentService


class PaymentController:
    def __init__(self) -> None:
        self.service = PaymentService()

    async def initiate(
        self,
        bill_id: UUID,
        req: PaymentInitiateRequest,
        current_user: User,
        db: AsyncSession,
    ):
        payment = await self.service.initiate_payment(
            bill_id=bill_id,
            initiated_by=current_user.id,
            db=db,
            payment_mode=req.payment_mode,
        )
        return {"status": "success", "data": payment}

    async def process(
        self,
        payment_id: UUID,
        req: PaymentProcessRequest,
        current_user: User,
        db: AsyncSession,
    ):
        payment = await self.service.process_payment(
            payment_id=payment_id,
            db=db,
            processed_by=current_user.id,
            force_success=req.force_success,
        )
        return {"status": "success", "data": payment}

    async def retry(
        self,
        payment_id: UUID,
        req: PaymentRetryRequest,
        current_user: User,
        db: AsyncSession,
    ):
        payment = await self.service.retry_payment(
            payment_id=payment_id,
            db=db,
            retried_by=current_user.id,
            force_success=req.force_success,
        )
        return {"status": "success", "data": payment}

    async def get(self, payment_id: UUID, current_user: User, db: AsyncSession):
        payment = await self.service.get_payment(payment_id=payment_id, current_user=current_user, db=db)
        return {"status": "success", "data": payment}

    async def list(
        self,
        current_user: User,
        db: AsyncSession,
        institution_id: Optional[int],
        status: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip: int = 0,
        limit: int = 10,
    ):
        _ = current_user
        rows, total = await self.service.list_payments(
            db=db,
            institution_id=institution_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
        import math
        return {
            "status": "success",
            "data": rows,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0
        }
