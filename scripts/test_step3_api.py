from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    body: Any | None = None

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (HTTP {self.status_code})"


def _parse_error(resp: httpx.Response) -> ApiError:
    try:
        payload = resp.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        return ApiError(
            status_code=resp.status_code,
            code=str(payload.get("code", "HTTP_ERROR")),
            message=str(payload.get("message", resp.text)),
            body=payload,
        )
    return ApiError(status_code=resp.status_code, code="HTTP_ERROR", message=resp.text, body=payload)


def _expect_ok(resp: httpx.Response) -> dict[str, Any]:
    if resp.status_code >= 400:
        raise _parse_error(resp)
    payload = resp.json()
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ApiError(resp.status_code, "INVALID_ENVELOPE", f"Unexpected response: {resp.text}", payload)
    return payload


def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise _parse_error(resp)
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise ApiError(resp.status_code, "LOGIN_FAILED", f"No access_token in response: {resp.text}", payload)
    return token


def main() -> int:
    start = date.today() + timedelta(days=1)
    end = date.today() + timedelta(days=10)

    with httpx.Client(timeout=30.0) as client:
        admin_token = login(client, "admin@chb.local", "Admin@123")
        principal_token = login(client, "principal@chb.local", "Principal@123")

        headers_principal = {"Authorization": f"Bearer {principal_token}"}
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        institution_id = int(os.getenv("INSTITUTION_ID", "1"))
        course_id = int(os.getenv("COURSE_ID", "1"))
        academic_year = os.getenv("ACADEMIC_YEAR", "2024-25")

        assessment = _expect_ok(
            client.get(
                f"{BASE_URL}/api/vacancies/assessment",
                headers=headers_principal,
                params={
                    "institution_id": institution_id,
                    "course_id": course_id,
                    "academic_year": academic_year,
                },
            )
        )
        if not assessment.get("data") or not assessment["data"].get("id"):
            raise ApiError(
                200,
                "ASSESSMENT_NOT_FOUND",
                "No vacancy assessment found for the given institution/course/academic_year",
                assessment,
            )

        assessment_id = assessment["data"]["id"]
        print(f"assessment_id={assessment_id}")

        print("1) Generate advertisement")
        gen = _expect_ok(
            client.post(
                f"{BASE_URL}/api/advertisements/generate",
                headers={**headers_principal, "Content-Type": "application/json"},
                json={
                    "assessment_id": assessment_id,
                    "application_start_date": str(start),
                    "application_end_date": str(end),
                },
            )
        )
        ad_id = gen["data"]["id"]
        print(f"   advertisement_id={ad_id}")

        print("2) Get advertisement")
        _expect_ok(client.get(f"{BASE_URL}/api/advertisements/{ad_id}", headers=headers_principal))

        print("3) Update advertisement")
        _expect_ok(
            client.put(
                f"{BASE_URL}/api/advertisements/{ad_id}",
                headers={**headers_principal, "Content-Type": "application/json"},
                json={
                    "content_en": "Updated EN content (script)",
                    "content_mr": "Updated MR content (script)",
                    "application_start_date": str(start),
                    "application_end_date": str(end),
                },
            )
        )

        print("4) Submit advertisement")
        submitted = _expect_ok(client.post(f"{BASE_URL}/api/advertisements/{ad_id}/submit", headers=headers_principal))
        if submitted["data"]["status"] != "REVIEW":
            raise ApiError(200, "INVALID_STATUS", f"Expected REVIEW, got {submitted['data']['status']}", submitted)

        print("5) Approve advertisement (ADMIN)")
        approved = _expect_ok(
            client.post(
                f"{BASE_URL}/api/advertisements/{ad_id}/approve",
                headers={**headers_admin, "Content-Type": "application/json"},
                json={"action": "APPROVE", "remarks": "Approved via script"},
            )
        )
        if approved["data"]["status"] != "APPROVED":
            raise ApiError(200, "INVALID_STATUS", f"Expected APPROVED, got {approved['data']['status']}", approved)

        print("6) Publish advertisement (ADMIN)")
        pub = _expect_ok(client.post(f"{BASE_URL}/api/advertisements/{ad_id}/publish", headers=headers_admin))
        public_token = pub["data"]["public_token"]
        print(f"   public_token={public_token}")

        print("7) Public fetch")
        public = _expect_ok(client.get(f"{BASE_URL}/api/advertisements/public/{public_token}"))
        # Ensure no internal IDs.
        forbidden = {"assessment_id", "institution_id", "course_id", "created_by", "approved_by"}
        present_forbidden = forbidden.intersection(public["data"].keys())
        if present_forbidden:
            raise ApiError(200, "PUBLIC_LEAK", f"Public response leaked fields: {sorted(present_forbidden)}", public)

        print("OK: Step 3 API flow completed")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        if exc.body is not None:
            print(json.dumps(exc.body, indent=2), file=sys.stderr)
        raise
