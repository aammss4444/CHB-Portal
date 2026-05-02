from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.payments.controller import PaymentController
from app.modules.payments.schemas import (
    PaymentInitiateRequest,
    PaymentProcessRequest,
    PaymentRetryRequest,
    PaymentTransactionResponse,
)
from app.dependencies.pagination import PaginationParams

router = APIRouter(prefix="/payments", tags=["Payments (Step 9)"])
controller = PaymentController()


@router.post("/initiate/{bill_id}", dependencies=[Depends(RoleChecker([RoleEnum.TREASURY, RoleEnum.ADMIN]))])
async def initiate_payment(
    bill_id: UUID,
    req: PaymentInitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await controller.initiate(bill_id=bill_id, req=req, current_user=current_user, db=db)
    result["data"] = PaymentTransactionResponse.model_validate(result["data"], from_attributes=True).model_dump()
    return result


@router.post("/process/{payment_id}", dependencies=[Depends(RoleChecker([RoleEnum.TREASURY]))])
async def process_payment(
    payment_id: UUID,
    req: PaymentProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await controller.process(payment_id=payment_id, req=req, current_user=current_user, db=db)
    result["data"] = PaymentTransactionResponse.model_validate(result["data"], from_attributes=True).model_dump()
    return result


@router.post("/retry/{payment_id}", dependencies=[Depends(RoleChecker([RoleEnum.TREASURY]))])
async def retry_payment(
    payment_id: UUID,
    req: PaymentRetryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await controller.retry(payment_id=payment_id, req=req, current_user=current_user, db=db)
    result["data"] = PaymentTransactionResponse.model_validate(result["data"], from_attributes=True).model_dump()
    return result


@router.get("/{payment_id}", dependencies=[Depends(RoleChecker([RoleEnum.ADMIN, RoleEnum.TREASURY, RoleEnum.FACULTY]))])
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await controller.get(payment_id=payment_id, current_user=current_user, db=db)
    result["data"] = PaymentTransactionResponse.model_validate(result["data"], from_attributes=True).model_dump()
    return result


@router.get("", dependencies=[Depends(RoleChecker([RoleEnum.ADMIN, RoleEnum.TREASURY]))])
async def list_payments(
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await controller.list(
        current_user=current_user,
        db=db,
        institution_id=institution_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    result["data"] = [PaymentTransactionResponse.model_validate(row, from_attributes=True).model_dump() for row in result["data"]]
    return result
