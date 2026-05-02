from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import and_, func, or_, select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.appointment_letter import AppointmentLetter
from app.models.attendance_anomaly import AnomalySeverity, AttendanceAnomaly
from app.models.chb_bill import BillStatus, CHBBill
from app.models.daily_attendance_summary import DailyAttendanceSummary
from app.models.faculty_credentials import FacultyCredentials
from app.models.lecture_log import LectureLog, LectureLogStatus
from app.models.user import RoleEnum, User

BASE_URL = "http://127.0.0.1:8000"
TEST_PASSWORD = "Test@123A"

ADMIN_EMAIL = "billing.admin@test.com"
PRINCIPAL_EMAIL = "billing.principal@test.com"
RO_EMAIL = "billing.ro@test.com"
DIRECTORATE_EMAIL = "billing.directorate@test.com"
TREASURY_EMAIL = "billing.treasury@test.com"


@dataclass
class ApiFailure(Exception):
    code: str
    message: str
    status_code: int

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (HTTP {self.status_code})"


def normalize_designation(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


def parse_body(resp: httpx.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"status": "error", "code": "HTTP_ERROR", "message": resp.text}


def expect_envelope(resp: httpx.Response) -> Any:
    body = parse_body(resp)
    if resp.status_code >= 400:
        raise ApiFailure(body.get("code", "HTTP_ERROR"), body.get("message", str(body)), resp.status_code)
    if body.get("status") != "success":
        raise ApiFailure("INVALID_ENVELOPE", str(body), resp.status_code)
    return body.get("data")


def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    body = parse_body(resp)
    if resp.status_code >= 400:
        raise ApiFailure(body.get("code", "HTTP_ERROR"), body.get("message", str(body)), resp.status_code)
    token = body.get("access_token")
    if not token:
        raise ApiFailure("INVALID_LOGIN_RESPONSE", str(body), resp.status_code)
    return token


async def ensure_user(
    *,
    email: str,
    role: RoleEnum,
    full_name: str,
    institution_id: int | None = None,
) -> User:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalars().first()
        if not user:
            user = User(
                email=email,
                hashed_password=get_password_hash(TEST_PASSWORD),
                role=role,
                full_name=full_name,
                institution_id=institution_id,
                is_active=True,
            )
            db.add(user)
        else:
            user.role = role
            user.full_name = full_name
            user.institution_id = institution_id
            user.hashed_password = get_password_hash(TEST_PASSWORD)
            user.is_active = True
        await db.commit()
        await db.refresh(user)
        return user


async def pick_billing_context() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(LectureLog, FacultyCredentials, AppointmentLetter, User)
                .join(FacultyCredentials, FacultyCredentials.id == LectureLog.faculty_credential_id)
                .join(AppointmentLetter, AppointmentLetter.id == FacultyCredentials.appointment_letter_id)
                .join(User, User.id == FacultyCredentials.user_id)
                .where(
                    FacultyCredentials.is_active.is_(True),
                    LectureLog.log_status == LectureLogStatus.VERIFIED.value,
                )
                .order_by(LectureLog.lecture_date.desc())
            )
        ).all()

        for log, credential, appointment, faculty_user in rows:
            period_start = log.lecture_date
            period_end = log.lecture_date

            unverified_count = int(
                (
                    await db.execute(
                        select(func.count(LectureLog.id)).where(
                            LectureLog.faculty_credential_id == credential.id,
                            LectureLog.academic_year == appointment.academic_year,
                            LectureLog.lecture_date == period_start,
                            LectureLog.log_status.in_([LectureLogStatus.DRAFT.value, LectureLogStatus.SUBMITTED.value]),
                        )
                    )
                ).scalar_one()
                or 0
            )
            if unverified_count > 0:
                continue

            high_unack_count = int(
                (
                    await db.execute(
                        select(func.count(AttendanceAnomaly.id))
                        .outerjoin(LectureLog, LectureLog.id == AttendanceAnomaly.lecture_log_id)
                        .outerjoin(DailyAttendanceSummary, DailyAttendanceSummary.id == AttendanceAnomaly.summary_id)
                        .where(
                            AttendanceAnomaly.faculty_credential_id == credential.id,
                            AttendanceAnomaly.severity == AnomalySeverity.HIGH.value,
                            AttendanceAnomaly.is_acknowledged.is_(False),
                            or_(
                                and_(
                                    LectureLog.id.is_not(None),
                                    LectureLog.lecture_date == period_start,
                                ),
                                and_(
                                    DailyAttendanceSummary.id.is_not(None),
                                    DailyAttendanceSummary.attendance_date == period_start,
                                ),
                            ),
                        )
                    )
                ).scalar_one()
                or 0
            )
            if high_unack_count > 0:
                continue

            existing_bill = (
                await db.execute(
                    select(CHBBill).where(
                        CHBBill.faculty_credential_id == credential.id,
                        CHBBill.period_start == period_start,
                        CHBBill.period_end == period_end,
                        CHBBill.bill_status != BillStatus.REJECTED.value,
                    )
                )
            ).scalars().first()
            if existing_bill:
                continue

            lecture_types = (
                await db.execute(
                    select(LectureLog.lecture_type)
                    .where(
                        LectureLog.faculty_credential_id == credential.id,
                        LectureLog.academic_year == appointment.academic_year,
                        LectureLog.lecture_date == period_start,
                        LectureLog.log_status == LectureLogStatus.VERIFIED.value,
                    )
                    .distinct()
                )
            ).scalars().all()

            return {
                "faculty_credential_id": credential.id,
                "faculty_user_id": faculty_user.id,
                "faculty_email": faculty_user.email,
                "institution_id": credential.institution_id,
                "academic_year": appointment.academic_year,
                "designation": normalize_designation(appointment.designation),
                "period_start": period_start,
                "period_end": period_end,
                "lecture_types_present": [str(x.value if hasattr(x, "value") else x) for x in lecture_types],
            }

    raise RuntimeError(
        "No eligible faculty/day found for Step 8 API test. "
        "Need at least one active faculty with VERIFIED logs and no blocking HIGH unacknowledged anomalies."
    )


async def prepare_logins(context: dict[str, Any]) -> None:
    await ensure_user(
        email=ADMIN_EMAIL,
        role=RoleEnum.ADMIN,
        full_name="Billing Admin",
    )
    await ensure_user(
        email=PRINCIPAL_EMAIL,
        role=RoleEnum.PRINCIPAL,
        full_name="Billing Principal",
        institution_id=context["institution_id"],
    )
    await ensure_user(
        email=RO_EMAIL,
        role=RoleEnum.RO,
        full_name="Billing RO",
    )
    await ensure_user(
        email=DIRECTORATE_EMAIL,
        role=RoleEnum.DIRECTORATE,
        full_name="Billing Directorate",
    )
    await ensure_user(
        email=TREASURY_EMAIL,
        role=RoleEnum.TREASURY,
        full_name="Billing Treasury",
    )

    async with AsyncSessionLocal() as db:
        faculty_user = (await db.execute(select(User).where(User.id == context["faculty_user_id"]))).scalars().first()
        if not faculty_user:
            raise RuntimeError("Faculty user missing for selected billing context")
        faculty_user.hashed_password = get_password_hash(TEST_PASSWORD)
        faculty_user.is_active = True
        await db.commit()


def build_rate_payload(context: dict[str, Any]) -> dict[str, Any]:
    base_rates = {
        "THEORY": Decimal("350.00"),
        "LAB": Decimal("375.00"),
        "TUTORIAL": Decimal("325.00"),
    }
    rates = []
    for lecture_type in ["THEORY", "LAB", "TUTORIAL"]:
        rates.append(
            {
                "designation": context["designation"],
                "lecture_type": lecture_type,
                "rate_per_lecture": str(base_rates[lecture_type]),
                "effective_from": str(context["period_start"]),
            }
        )
    return {
        "institution_id": context["institution_id"],
        "academic_year": context["academic_year"],
        "rates": rates,
    }


async def amain() -> None:
    context = await pick_billing_context()
    await prepare_logins(context)

    print("Using context:")
    print(
        f"  faculty_credential_id={context['faculty_credential_id']}, "
        f"institution_id={context['institution_id']}, "
        f"period={context['period_start']}..{context['period_end']}, "
        f"designation={context['designation']}"
    )

    with httpx.Client(timeout=90.0) as client:
        admin_token = login(client, ADMIN_EMAIL, TEST_PASSWORD)
        principal_token = login(client, PRINCIPAL_EMAIL, TEST_PASSWORD)
        ro_token = login(client, RO_EMAIL, TEST_PASSWORD)
        directorate_token = login(client, DIRECTORATE_EMAIL, TEST_PASSWORD)
        treasury_token = login(client, TREASURY_EMAIL, TEST_PASSWORD)
        faculty_token = login(client, context["faculty_email"], TEST_PASSWORD)

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        principal_headers = {"Authorization": f"Bearer {principal_token}"}
        ro_headers = {"Authorization": f"Bearer {ro_token}"}
        directorate_headers = {"Authorization": f"Bearer {directorate_token}"}
        treasury_headers = {"Authorization": f"Bearer {treasury_token}"}
        faculty_headers = {"Authorization": f"Bearer {faculty_token}"}

        print("1) POST /billing/rates")
        created_rates = expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/rates",
                headers=admin_headers,
                json=build_rate_payload(context),
            )
        )
        print(f"   rates upserted: {len(created_rates)}")

        print("2) GET /billing/rates")
        grouped_rates = expect_envelope(
            client.get(
                f"{BASE_URL}/api/billing/rates",
                headers=principal_headers,
                params={
                    "institution_id": context["institution_id"],
                    "academic_year": context["academic_year"],
                    "designation": context["designation"],
                },
            )
        )
        designation_rates = grouped_rates.get(context["designation"], [])
        if not designation_rates:
            raise RuntimeError("GET /billing/rates returned no rows for selected designation")
        print(f"   designation entries: {len(designation_rates)}")

        print("3) PUT /billing/rates/{rate_id}")
        editable_rate_id = designation_rates[0]["id"]
        updated_rate = expect_envelope(
            client.put(
                f"{BASE_URL}/api/billing/rates/{editable_rate_id}",
                headers=admin_headers,
                json={"rate_per_lecture": "355.00"},
            )
        )
        print(f"   updated rate: {updated_rate['id']}")

        print("4) POST /billing/generate")
        bill = expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/generate",
                headers=principal_headers,
                json={
                    "faculty_credential_id": str(context["faculty_credential_id"]),
                    "period_start": str(context["period_start"]),
                    "period_end": str(context["period_end"]),
                    "academic_year": context["academic_year"],
                },
            )
        )
        bill_id = bill["id"]
        bill_number = bill["bill_number"]
        print(f"   bill generated: {bill_number}")

        print("5) POST /billing/generate/bulk")
        bulk_result = expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/generate/bulk",
                headers=admin_headers,
                json={
                    "institution_id": context["institution_id"],
                    "period_start": str(context["period_start"]),
                    "period_end": str(context["period_end"]),
                    "academic_year": context["academic_year"],
                },
            )
        )
        print(f"   success_count={bulk_result['success_count']}, skipped={len(bulk_result['skipped'])}")

        print("6) POST /billing/bills/{bill_id}/submit")
        submitted = expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/submit",
                headers=principal_headers,
                json={},
            )
        )
        print(f"   status={submitted['bill_status']}")

        print("7) POST /billing/bills/{bill_id}/approve (PRINCIPAL REJECT)")
        rejected = expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/approve",
                headers=principal_headers,
                json={"action": "REJECT", "remarks": "Testing regeneration path"},
            )
        )
        print(f"   status={rejected['bill_status']}, rejection_stage={rejected['rejection_stage']}")

        print("8) GET /billing/bills/{bill_id}/approvals")
        approvals_before_regen = expect_envelope(
            client.get(f"{BASE_URL}/api/billing/bills/{bill_id}/approvals", headers=admin_headers)
        )
        print(f"   history count before regen={len(approvals_before_regen['history'])}")

        print("12) POST /billing/bills/{bill_id}/regenerate")
        regenerated = expect_envelope(
            client.post(f"{BASE_URL}/api/billing/bills/{bill_id}/regenerate", headers=principal_headers)
        )
        if regenerated["bill_number"] != bill_number:
            raise RuntimeError("Regeneration changed bill_number; expected to retain original bill number")
        print(f"   regenerated: {regenerated['bill_number']} (retained)")

        print("6b) POST /billing/bills/{bill_id}/submit")
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/submit",
                headers=principal_headers,
                json={},
            )
        )
        print("   resubmitted")

        print("7b) Approval chain APPROVE: PRINCIPAL -> RO -> DIRECTORATE -> TREASURY")
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/approve",
                headers=principal_headers,
                json={"action": "APPROVE"},
            )
        )
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/approve",
                headers=ro_headers,
                json={"action": "APPROVE"},
            )
        )
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/approve",
                headers=directorate_headers,
                json={"action": "APPROVE"},
            )
        )
        processed = expect_envelope(
            client.post(
                f"{BASE_URL}/api/billing/bills/{bill_id}/approve",
                headers=treasury_headers,
                json={"action": "APPROVE"},
            )
        )
        print(f"   final_status={processed['bill_status']}, is_locked={processed['is_locked']}")

        print("8b) GET /billing/bills/{bill_id}/approvals")
        approvals_after = expect_envelope(
            client.get(f"{BASE_URL}/api/billing/bills/{bill_id}/approvals", headers=admin_headers)
        )
        print(
            f"   history count after full chain={len(approvals_after['history'])}, "
            f"pending={approvals_after['current_approver_role']}"
        )

        print("9) GET /billing/bills (FACULTY)")
        faculty_bills = expect_envelope(client.get(f"{BASE_URL}/api/billing/bills", headers=faculty_headers))
        print(f"   faculty-visible bills={len(faculty_bills)}")

        print("9b) GET /billing/bills (RO queue)")
        ro_queue = expect_envelope(client.get(f"{BASE_URL}/api/billing/bills", headers=ro_headers))
        print(f"   RO queue bills={len(ro_queue)}")

        print("10) GET /billing/bills/{bill_id} (FACULTY)")
        detail = expect_envelope(
            client.get(f"{BASE_URL}/api/billing/bills/{bill_id}", headers=faculty_headers)
        )
        print(
            f"   line_items={len(detail['line_items'])}, approvals={len(detail['approval_chain'])}, "
            f"status={detail['bill_status']}"
        )

        print("11) GET /billing/bills/summary")
        summary = expect_envelope(
            client.get(
                f"{BASE_URL}/api/billing/bills/summary",
                headers=principal_headers,
                params={
                    "institution_id": context["institution_id"],
                    "academic_year": context["academic_year"],
                    "month": int(context["period_start"].month),
                },
            )
        )
        print(
            "   summary:",
            f"generated={summary['total_bills_generated']},",
            f"processed={summary['bills_processed']}",
        )

        print("3b) PUT /billing/rates/{rate_id} expect RATE_IN_USE")
        try:
            expect_envelope(
                client.put(
                    f"{BASE_URL}/api/billing/rates/{editable_rate_id}",
                    headers=admin_headers,
                    json={"rate_per_lecture": "365.00"},
                )
            )
            raise RuntimeError("Expected RATE_IN_USE but endpoint returned success")
        except ApiFailure as exc:
            if exc.code != "RATE_IN_USE":
                raise
            print(f"   expected conflict: {exc.code}")

        print("\nOK: Step 8 API flow passed.")


if __name__ == "__main__":
    asyncio.run(amain())
