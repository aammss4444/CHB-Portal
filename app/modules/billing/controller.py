from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.billing.schemas import (
    BillApprovalRequest,
    BillGenerateRequest,
    BulkBillGenerateRequest,
    RateMasterCreateRequest,
    RateMasterUpdateRequest,
)
from app.modules.billing.service import BillingService


class BillingController:
    def __init__(self) -> None:
        self.service = BillingService()

    async def create_rates(self, db: AsyncSession, current_user: User, req: RateMasterCreateRequest):
        data = await self.service.bulk_upsert_rates(db, current_user, req)
        return {"status": "success", "data": data}

    async def get_rates(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: int,
        academic_year: str,
        designation: Optional[str],
    ):
        data = await self.service.get_rates(db, current_user, institution_id, academic_year, designation)
        return {"status": "success", "data": data}

    async def update_rate(self, db: AsyncSession, current_user: User, rate_id: UUID, req: RateMasterUpdateRequest):
        data = await self.service.update_rate(db, current_user, rate_id, req)
        return {"status": "success", "data": data}

    async def generate_bill(self, db: AsyncSession, current_user: User, req: BillGenerateRequest):
        data = await self.service.generate_bill_endpoint(db, current_user, req)
        return {"status": "success", "data": data}

    async def generate_bulk(self, db: AsyncSession, current_user: User, req: BulkBillGenerateRequest):
        data = await self.service.generate_bulk_bills(db, current_user, req)
        return {"status": "success", "data": data}

    async def submit_bill(self, db: AsyncSession, current_user: User, bill_id: UUID):
        data = await self.service.submit_bill(db, current_user, bill_id)
        return {"status": "success", "data": data}

    async def approve_bill(self, db: AsyncSession, current_user: User, bill_id: UUID, req: BillApprovalRequest):
        data = await self.service.approve_bill_endpoint(db, current_user, bill_id, req)
        return {"status": "success", "data": data}

    async def get_bill_approvals(self, db: AsyncSession, current_user: User, bill_id: UUID):
        data = await self.service.get_bill_approvals(db, current_user, bill_id)
        return {"status": "success", "data": data}

    async def list_bills(
        self,
        db: AsyncSession,
        current_user: User,
        faculty_credential_id: Optional[UUID],
        institution_id: Optional[int],
        course_id: Optional[int],
        academic_year: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date],
        bill_status: Optional[str],
        current_approver_role: Optional[str],
        skip: int = 0,
        limit: int = 10,
    ):
        data, total = await self.service.list_bills(
            db=db,
            current_user=current_user,
            faculty_credential_id=faculty_credential_id,
            institution_id=institution_id,
            course_id=course_id,
            academic_year=academic_year,
            period_start=period_start,
            period_end=period_end,
            bill_status=bill_status,
            current_approver_role=current_approver_role,
            skip=skip,
            limit=limit,
        )
        import math
        return {
            "status": "success",
            "data": data,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0
        }

    async def get_bill_detail(self, db: AsyncSession, current_user: User, bill_id: UUID):
        data = await self.service.get_bill_detail(db, current_user, bill_id)
        return {"status": "success", "data": data}

    async def get_bill_summary(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: Optional[int],
        academic_year: Optional[str],
        month: Optional[int],
        bill_status: Optional[str],
    ):
        data = await self.service.get_institution_summary(
            db, current_user, institution_id, academic_year, month, bill_status
        )
        return {"status": "success", "data": data}

    async def regenerate_bill(self, db: AsyncSession, current_user: User, bill_id: UUID):
        data = await self.service.regenerate_bill(db, current_user, bill_id)
        return {"status": "success", "data": data}

