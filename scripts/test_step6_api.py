from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import and_, select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.appointment_letter import AppointmentLetter
from app.models.candidate import Candidate
from app.models.selection_result import FinalResultStatus, SelectionResult, SelectionResultStatus
from app.models.user import RoleEnum, User

BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "api.admin@test.com"
PRINCIPAL_EMAIL = "api.principal@test.com"
TEST_PASSWORD = "Test@123A"


@dataclass
class ApiFailure(Exception):
    code: str
    message: str
    status_code: int

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (HTTP {self.status_code})"


def parse_body(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"status": "error", "code": "HTTP_ERROR", "message": resp.text}


def expect_envelope(resp: httpx.Response) -> dict:
    body = parse_body(resp)
    if resp.status_code >= 400:
        raise ApiFailure(body.get("code", "HTTP_ERROR"), body.get("message", str(body)), resp.status_code)
    if body.get("status") != "success":
        raise ApiFailure("INVALID_ENVELOPE", str(body), resp.status_code)
    return body.get("data", body)


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


async def get_test_data() -> tuple[UUID, str, int, str]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(SelectionResult, Candidate, User)
            .join(Candidate, Candidate.id == SelectionResult.candidate_id)
            .join(User, User.id == Candidate.user_id)
            .outerjoin(AppointmentLetter, AppointmentLetter.selection_result_id == SelectionResult.id)
            .where(
                and_(
                    SelectionResult.status == FinalResultStatus.CONFIRMED.value,
                    SelectionResult.result_status == SelectionResultStatus.SELECTED.value,
                    AppointmentLetter.id.is_(None),
                )
            )
            .order_by(SelectionResult.created_at.desc())
        )
        row = (await db.execute(stmt)).first()

        if not row:
            raise RuntimeError(
                "No eligible CONFIRMED+SELECTED result without appointment letter found. "
                "Run Step 5 flow first, then retry Step 6 test."
            )

        selection_result, _, user = row
        return selection_result.id, user.email, selection_result.institution_id, selection_result.academic_year


async def get_resume_data() -> tuple[str, str, int, str, str] | None:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AppointmentLetter, User)
            .join(Candidate, Candidate.id == AppointmentLetter.candidate_id)
            .join(User, User.id == Candidate.user_id)
            .where(
                AppointmentLetter.status.in_(
                    ["DRAFT", "REJECTED", "PENDING_APPROVAL", "APPROVED", "ISSUED", "ACCEPTED"]
                )
            )
            .order_by(AppointmentLetter.created_at.desc())
        )
        row = (await db.execute(stmt)).first()
        if not row:
            return None

        letter, user = row
        return str(letter.id), letter.status, letter.institution_id, letter.academic_year, user.email


async def ensure_api_users(institution_id: int) -> tuple[str, str, str]:
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).where(User.email == ADMIN_EMAIL))).scalars().first()
        if not admin:
            admin = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(TEST_PASSWORD),
                role=RoleEnum.ADMIN,
                full_name="API Admin",
            )
            db.add(admin)
        else:
            admin.role = RoleEnum.ADMIN
            admin.hashed_password = get_password_hash(TEST_PASSWORD)
            admin.is_active = True

        principal = (await db.execute(select(User).where(User.email == PRINCIPAL_EMAIL))).scalars().first()
        if not principal:
            principal = User(
                email=PRINCIPAL_EMAIL,
                hashed_password=get_password_hash(TEST_PASSWORD),
                role=RoleEnum.PRINCIPAL,
                full_name="API Principal",
                institution_id=institution_id,
            )
            db.add(principal)
        else:
            principal.role = RoleEnum.PRINCIPAL
            principal.institution_id = institution_id
            principal.hashed_password = get_password_hash(TEST_PASSWORD)
            principal.is_active = True

        await db.commit()

    return ADMIN_EMAIL, PRINCIPAL_EMAIL, TEST_PASSWORD


async def amain() -> None:
    selection_result_id: UUID | None = None
    appointment_id: str | None = None
    current_status: str | None = None

    try:
        selection_result_id, candidate_email, institution_id, academic_year = await get_test_data()
    except RuntimeError:
        resume = await get_resume_data()
        if not resume:
            raise
        appointment_id, current_status, institution_id, academic_year, candidate_email = resume
        print(f"Resuming with existing appointment: {appointment_id} ({current_status})")

    admin_email, principal_email, api_password = await ensure_api_users(institution_id)
    joining_date = date.today() + timedelta(days=15)
    acceptance_deadline = date.today() + timedelta(days=10)

    with httpx.Client(timeout=60.0) as client:
        admin_token = login(client, admin_email, api_password)
        principal_token = login(client, principal_email, api_password)
        candidate_token = login(client, candidate_email, "Candidate@123")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        principal_headers = {"Authorization": f"Bearer {principal_token}"}
        candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

        if appointment_id is None:
            print("1) POST /appointments/generate")
            generated = expect_envelope(
                client.post(
                    f"{BASE_URL}/api/appointments/generate",
                    headers=principal_headers,
                    json={
                        "selection_result_id": str(selection_result_id),
                        "joining_date": str(joining_date),
                        "salary_per_lecture": str(Decimal("850.00")),
                        "acceptance_deadline": str(acceptance_deadline),
                    },
                )
            )
            appointment_id = generated["id"]
            current_status = generated["status"]
            print(f"   appointment_id: {appointment_id}, status: {current_status}")
        else:
            print("1) POST /appointments/generate")
            print("   skipped: no fresh eligible selection result in current DB state")

        print("2) GET /appointments/{id} (principal)")
        letter = expect_envelope(
            client.get(f"{BASE_URL}/api/appointments/{appointment_id}", headers=principal_headers)
        )
        current_status = letter["status"]
        print(f"   fetched: {letter['appointment_number']} ({current_status})")

        print("3) PUT /appointments/{id}")
        if current_status in {"DRAFT", "REJECTED"}:
            updated = expect_envelope(
                client.put(
                    f"{BASE_URL}/api/appointments/{appointment_id}",
                    headers=principal_headers,
                    json={
                        "salary_per_lecture": "900.00",
                        "joining_date": str(joining_date),
                        "acceptance_deadline": str(acceptance_deadline),
                    },
                )
            )
            current_status = updated["status"]
            print(f"   updated salary: {updated['salary_per_lecture']}")
        else:
            print(f"   skipped: appointment is {current_status}, not editable")

        print("4) POST /appointments/{id}/submit")
        if current_status in {"DRAFT", "REJECTED"}:
            submitted = expect_envelope(
                client.post(f"{BASE_URL}/api/appointments/{appointment_id}/submit", headers=principal_headers)
            )
            current_status = submitted["status"]
            print(f"   status: {current_status}")
        else:
            print(f"   skipped: appointment is {current_status}, not submittable")

        print("5) POST /appointments/{id}/approve")
        if current_status == "PENDING_APPROVAL":
            approved = expect_envelope(
                client.post(
                    f"{BASE_URL}/api/appointments/{appointment_id}/approve",
                    headers=admin_headers,
                    json={"action": "APPROVE"},
                )
            )
            current_status = approved["status"]
            print(f"   status: {current_status}")
        else:
            print(f"   skipped: appointment is {current_status}, not approvable")

        print("6) POST /appointments/{id}/issue")
        if current_status == "APPROVED":
            issued = expect_envelope(
                client.post(f"{BASE_URL}/api/appointments/{appointment_id}/issue", headers=admin_headers)
            )
            print(f"   issued_at: {issued['issued_at']}")
            current_status = "ISSUED"
        else:
            print(f"   skipped: appointment is {current_status}, not issuable")

        print("7) GET /appointments/{id} (candidate)")
        cand_view = expect_envelope(
            client.get(f"{BASE_URL}/api/appointments/{appointment_id}", headers=candidate_headers)
        )
        current_status = cand_view["status"]
        print(f"   candidate download_url present: {bool(cand_view.get('download_url'))}")

        print("8) POST /appointments/{id}/respond (candidate ACCEPTED)")
        if current_status == "ISSUED":
            responded = expect_envelope(
                client.post(
                    f"{BASE_URL}/api/appointments/{appointment_id}/respond",
                    headers=candidate_headers,
                    json={"action": "ACCEPTED", "remarks": "Accepting offer."},
                )
            )
            current_status = responded["status"]
            print(f"   status: {current_status}")
        else:
            print(f"   skipped: appointment is {current_status}, not candidate-respondable")

        print("9) GET /appointments/institution/{institution_id}")
        listed = expect_envelope(
            client.get(
                f"{BASE_URL}/api/appointments/institution/{institution_id}",
                headers=principal_headers,
                params={"academic_year": academic_year, "page": 1, "size": 20},
            )
        )
        print(f"   total: {listed['total']}, page-size: {listed['size']}")

        print("10) POST /appointments/{id}/credentials (expect 409 after ACCEPTED auto-issue)")
        try:
            expect_envelope(
                client.post(f"{BASE_URL}/api/appointments/{appointment_id}/credentials", headers=admin_headers)
            )
            raise RuntimeError("Expected CREDENTIALS_ALREADY_ISSUED but endpoint returned success")
        except ApiFailure as exc:
            if exc.code != "CREDENTIALS_ALREADY_ISSUED":
                raise
            print(f"   expected conflict: {exc.code}")

        print("\nOK: Step 6 API test flow passed.")


if __name__ == "__main__":
    asyncio.run(amain())
