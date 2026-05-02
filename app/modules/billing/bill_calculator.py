from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BillCalculationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LectureLogInput(BaseModel):
    id: UUID
    faculty_credential_id: UUID
    lecture_date: date
    slot_number: int
    subject_name: str
    lecture_type: str
    class_name: str | None = None
    is_extra: bool = False
    is_substitute: bool = False
    log_status: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BillLineItemInput(BaseModel):
    lecture_log_id: UUID
    lecture_date: date
    slot_number: int
    subject_name: str
    lecture_type: str
    class_name: str | None = None
    rate_per_lecture: Decimal
    amount: Decimal
    is_extra: bool = False
    is_substitute: bool = False


class BillCalculationInput(BaseModel):
    faculty_credential_id: UUID
    designation: str
    period_start: date
    period_end: date
    verified_logs: List[LectureLogInput]
    rate_map: Dict[Tuple[str, str], Decimal]
    max_daily_lectures: int


class BillCalculationOutput(BaseModel):
    total_theory_lectures: int
    total_lab_lectures: int
    total_tutorial_lectures: int
    total_extra_lectures: int
    total_substitute_lectures: int
    total_billable_lectures: int
    gross_amount: Decimal
    line_items: List[BillLineItemInput]


def _resolve_line_lecture_type(log: LectureLogInput) -> str:
    if log.is_substitute:
        return "SUBSTITUTE"
    if log.is_extra:
        return "EXTRA"
    return log.lecture_type


def calculate_bill(payload: BillCalculationInput) -> BillCalculationOutput:
    """Calculate CHB bill totals from already-fetched attendance logs and rate map."""
    filtered_logs = [
        log
        for log in payload.verified_logs
        if log.log_status == "VERIFIED" and payload.period_start <= log.lecture_date <= payload.period_end
    ]

    by_date: dict[date, list[LectureLogInput]] = defaultdict(list)
    for row in filtered_logs:
        by_date[row.lecture_date].append(row)

    included_logs: list[LectureLogInput] = []
    for lecture_date, logs in by_date.items():
        _ = lecture_date
        ordered = sorted(
            logs,
            key=lambda item: (
                item.slot_number,
                item.created_at or datetime.min,
                str(item.id),
            ),
        )
        included_logs.extend(ordered[: payload.max_daily_lectures])

    line_items: list[BillLineItemInput] = []
    gross_amount = Decimal("0.00")
    theory_count = 0
    lab_count = 0
    tutorial_count = 0
    extra_count = 0
    substitute_count = 0

    for log in included_logs:
        rate_key = (payload.designation, log.lecture_type)
        rate = payload.rate_map.get(rate_key)
        if rate is None:
            raise BillCalculationError(
                code="RATE_NOT_FOUND",
                message=f"RATE_NOT_FOUND for designation={payload.designation}, lecture_type={log.lecture_type}",
            )

        billed_type = _resolve_line_lecture_type(log)
        amount = rate * Decimal("1")
        gross_amount += amount

        if billed_type == "THEORY":
            theory_count += 1
        elif billed_type == "LAB":
            lab_count += 1
        elif billed_type == "TUTORIAL":
            tutorial_count += 1
        elif billed_type == "EXTRA":
            extra_count += 1
        elif billed_type == "SUBSTITUTE":
            substitute_count += 1

        line_items.append(
            BillLineItemInput(
                lecture_log_id=log.id,
                lecture_date=log.lecture_date,
                slot_number=log.slot_number,
                subject_name=log.subject_name,
                lecture_type=billed_type,
                class_name=log.class_name,
                rate_per_lecture=rate,
                amount=amount,
                is_extra=log.is_extra,
                is_substitute=log.is_substitute,
            )
        )

    return BillCalculationOutput(
        total_theory_lectures=theory_count,
        total_lab_lectures=lab_count,
        total_tutorial_lectures=tutorial_count,
        total_extra_lectures=extra_count,
        total_substitute_lectures=substitute_count,
        total_billable_lectures=len(line_items),
        gross_amount=gross_amount,
        line_items=line_items,
    )
