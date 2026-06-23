from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.billing.controller import BillingController
from app.modules.billing.schemas import (
    BillApprovalRequest,
    BillGenerateRequest,
    BillSubmitRequest,
    BulkBillGenerateRequest,
    RateMasterCreateRequest,
    RateMasterUpdateRequest,
)
from app.dependencies.pagination import PaginationParams

router = APIRouter(prefix="/billing", tags=["Billing (Step 8)"])
controller = BillingController()

admin_only = RoleChecker([RoleEnum.ADMIN])
admin_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])
approval_roles = RoleChecker([RoleEnum.PRINCIPAL, RoleEnum.RO, RoleEnum.DIRECTORATE, RoleEnum.TREASURY])
billing_read_roles = RoleChecker(
    [RoleEnum.FACULTY, RoleEnum.PRINCIPAL, RoleEnum.ADMIN, RoleEnum.RO, RoleEnum.DIRECTORATE, RoleEnum.TREASURY]
)
rates_read_roles = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])


@router.post("/rates", dependencies=[Depends(admin_only)])
async def create_rates(
    req: RateMasterCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.create_rates(db, current_user, req)


@router.get("/rates", dependencies=[Depends(rates_read_roles)])
async def list_rates(
    institution_id: int = Query(...),
    academic_year: str = Query(...),
    designation: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_rates(db, current_user, institution_id, academic_year, designation)


@router.put("/rates/{rate_id}", dependencies=[Depends(admin_only)])
async def update_rate(
    rate_id: UUID,
    req: RateMasterUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.update_rate(db, current_user, rate_id, req)


@router.post("/generate", dependencies=[Depends(admin_principal)])
async def generate_bill(
    req: BillGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.generate_bill(db, current_user, req)


@router.post("/generate/bulk", dependencies=[Depends(admin_only)])
async def generate_bulk(
    req: BulkBillGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.generate_bulk(db, current_user, req)


@router.post("/bills/{bill_id}/submit", dependencies=[Depends(RoleChecker([RoleEnum.PRINCIPAL]))])
async def submit_bill(
    bill_id: UUID,
    req: Optional[BillSubmitRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = req
    return await controller.submit_bill(db, current_user, bill_id)


@router.post("/bills/{bill_id}/approve", dependencies=[Depends(approval_roles)])
async def approve_bill(
    bill_id: UUID,
    req: BillApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # STEP 9 GATE: Treasury-processed bills feed payment disbursement in Step 9
    return await controller.approve_bill(db, current_user, bill_id, req)


@router.get("/bills/{bill_id}/approvals", dependencies=[Depends(billing_read_roles)])
async def get_bill_approvals(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_bill_approvals(db, current_user, bill_id)


@router.get("/bills", dependencies=[Depends(billing_read_roles)])
async def list_bills(
    pagination: PaginationParams = Depends(),
    faculty_credential_id: Optional[UUID] = Query(None),
    institution_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    bill_status: Optional[str] = Query(None),
    current_approver_role: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_bills(
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
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/bills/summary", dependencies=[Depends(RoleChecker([RoleEnum.PRINCIPAL, RoleEnum.ADMIN, RoleEnum.RO, RoleEnum.TREASURY]))])
async def get_bill_summary(
    institution_id: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    bill_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_bill_summary(db, current_user, institution_id, academic_year, month, bill_status)


@router.get("/bills/{bill_id}", dependencies=[Depends(billing_read_roles)])
async def get_bill_detail(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_bill_detail(db, current_user, bill_id)


@router.post("/bills/{bill_id}/regenerate", dependencies=[Depends(admin_principal)])
async def regenerate_bill(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.regenerate_bill(db, current_user, bill_id)


# AI Endpoints

@router.post("/{bill_id}/ai-validate", dependencies=[Depends(approval_roles)])
async def ai_validate_bill(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_validate_bill(db, current_user, bill_id)

@router.get("/{bill_id}/ai-readiness", dependencies=[Depends(approval_roles)])
async def ai_readiness(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_readiness(db, current_user, bill_id)

@router.get("/ai-monitor", dependencies=[Depends(admin_only)])
async def ai_monitor(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_monitor(db, current_user)

@router.post("/{bill_id}/ai-snapshot", dependencies=[Depends(approval_roles)])
async def ai_snapshot(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_snapshot(db, current_user, bill_id)
