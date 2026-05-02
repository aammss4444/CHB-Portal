from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentInitiateRequest(BaseModel):
    payment_mode: str = "BANK_TRANSFER"


class PaymentProcessRequest(BaseModel):
    force_success: Optional[bool] = None


class PaymentRetryRequest(BaseModel):
    force_success: Optional[bool] = None


class PaymentTransactionResponse(BaseModel):
    id: UUID
    bill_id: UUID
    faculty_credential_id: UUID
    amount: Decimal
    payment_status: str
    payment_mode: str
    transaction_reference: Optional[str] = None
    bank_reference: Optional[str] = None
    failure_reason: Optional[str] = None
    initiated_at: datetime
    processed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
