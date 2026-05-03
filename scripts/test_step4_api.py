from __future__ import annotations

import asyncio
import io
import time
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

import httpx
from PIL import Image
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.advertisement import Advertisement, AdvertisementStatus


BASE_URL = "http://127.0.0.1:8000"


@dataclass
class ApiFailure(Exception):
    code: str
    message: str
    status_code: int

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (HTTP {self.status_code})"


def expect_envelope(resp: httpx.Response) -> dict:
    try:
        body = resp.json()
    except Exception:
        raise ApiFailure("HTTP_ERROR", resp.text, resp.status_code)
    if resp.status_code >= 400:
        raise ApiFailure(body.get("code", "HTTP_ERROR"), body.get("message", str(body)), resp.status_code)
    if body.get("status") != "success":
        raise ApiFailure("INVALID_ENVELOPE", str(body), resp.status_code)
    return body["data"]


async def get_published_advertisement_id() -> UUID:
    async with AsyncSessionLocal() as db:
        ad = (
            await db.execute(
                select(Advertisement)
                .where(Advertisement.status == AdvertisementStatus.PUBLISHED.value)
                .order_by(Advertisement.created_at.desc())
            )
        ).scalars().first()
        if not ad:
            raise RuntimeError("No published advertisement found. Publish one Step 3 advertisement first.")
        today = date.today()
        if not ad.application_start_date or not ad.application_end_date or not (
            ad.application_start_date <= today <= ad.application_end_date
        ):
            ad.application_start_date = today - timedelta(days=1)
            ad.application_end_date = today + timedelta(days=15)
            await db.commit()
        return ad.id


def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    body = resp.json()
    if resp.status_code >= 400:
        raise ApiFailure(body.get("code", "HTTP_ERROR"), body.get("message", str(body)), resp.status_code)
    return body["access_token"]


def image_bytes(seed: int) -> bytes:
    image = Image.new("RGB", (300, 300), color=(seed % 255, (seed * 2) % 255, (seed * 3) % 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> int:
    ad_id = asyncio.run(get_published_advertisement_id())
    stamp = int(time.time())
    candidate_email = f"candidate{stamp}@example.com"
    candidate_password = "Candidate@123"

    # Document upload triggers background AI/OCR hooks; keep generous timeout for local LLM latency.
    with httpx.Client(timeout=120.0) as client:
        # Register candidate (idempotent enough for new timestamp)
        register = client.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": candidate_email,
                "password": candidate_password,
                "role": "CANDIDATE",
                "full_name": f"Candidate {stamp}",
                "phone_number": f"99999{str(stamp)[-5:]}",
            },
        )
        if register.status_code >= 400:
            body = register.json()
            raise ApiFailure(body.get("code", "HTTP_ERROR"), body.get("message", str(body)), register.status_code)

        candidate_token = login(client, candidate_email, candidate_password)
        principal_token = login(client, "principal@chb.local", "Principal@123")

        candidate_headers = {"Authorization": f"Bearer {candidate_token}"}
        principal_headers = {"Authorization": f"Bearer {principal_token}"}

        # 1) profile
        print("1) POST /candidates/profile")
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/candidates/profile",
                headers=candidate_headers,
                json={
                    "full_name": f"Candidate {stamp}",
                    "father_name": "Parent Name",
                    "date_of_birth": str(date.today() - timedelta(days=365 * 25)),
                    "gender": "MALE",
                    "category": "OPEN",
                    "religion": "Hindu",
                    "nationality": "Indian",
                    "mobile": "9876543210",
                    "email": candidate_email,
                    "address": "Some Address, Pune",
                    "district": "Pune",
                    "state": "Maharashtra",
                    "pincode": "411001",
                    "aadhar_number": f"{stamp}123456",
                },
            )
        )

        # 2) qualifications
        print("2) POST /candidates/qualifications")
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/candidates/qualifications",
                headers=candidate_headers,
                json={
                    "qualifications": [
                        {
                            "degree": "ME",
                            "specialization": "Computer",
                            "university": "SPPU",
                            "year_of_passing": date.today().year - 3,
                            "percentage": 78.5,
                            "is_highest": True,
                        }
                    ]
                },
            )
        )

        # 3) experience
        print("3) POST /candidates/experience")
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/candidates/experience",
                headers=candidate_headers,
                json={
                    "experiences": [
                        {
                            "institution_name": "ABC Institute",
                            "designation": "Lecturer",
                            "from_date": str(date.today() - timedelta(days=365 * 2)),
                            "to_date": str(date.today() - timedelta(days=365)),
                            "is_current": False,
                            "experience_type": "TEACHING",
                        }
                    ]
                },
            )
        )

        # 4) create app
        print("4) POST /applications")
        app_data = expect_envelope(
            client.post(
                f"{BASE_URL}/api/applications",
                headers=candidate_headers,
                json={"advertisement_id": str(ad_id), "applied_designation": "Assistant Professor"},
            )
        )
        application_id = app_data["id"]

        # 5) upload required documents
        for idx, doc_type in enumerate(["PHOTO", "SIGNATURE", "AADHAR", "DEGREE_CERTIFICATE", "MARKSHEET"]):
            print(f"5.{idx+1}) upload {doc_type}")
            img = image_bytes(idx + 1)
            files = {"file": (f"{doc_type.lower()}.png", img, "image/png")}
            data = {"document_type": doc_type}
            expect_envelope(
                client.post(
                    f"{BASE_URL}/api/applications/{application_id}/documents",
                    headers=candidate_headers,
                    data=data,
                    files=files,
                )
            )

        # 6) list docs as candidate
        print("6) GET /applications/{id}/documents (candidate)")
        expect_envelope(
            client.get(
                f"{BASE_URL}/api/applications/{application_id}/documents",
                headers=candidate_headers,
            )
        )

        # 7) submit app
        print("7) POST /applications/{id}/submit")
        expect_envelope(
            client.post(
                f"{BASE_URL}/api/applications/{application_id}/submit",
                headers=candidate_headers,
                json={"declaration_accepted": True},
            )
        )

        # 8) my applications
        print("8) GET /applications/my")
        expect_envelope(client.get(f"{BASE_URL}/api/applications/my", headers=candidate_headers))

        # 9) list docs as principal
        print("9) GET /applications/{id}/documents (principal)")
        expect_envelope(
            client.get(
                f"{BASE_URL}/api/applications/{application_id}/documents",
                headers=principal_headers,
            )
        )

        # 10) list applications principal filter by ad
        print("10) GET /applications (principal)")
        expect_envelope(
            client.get(
                f"{BASE_URL}/api/applications",
                headers=principal_headers,
                params={"advertisement_id": str(ad_id)},
            )
        )

        print("OK: Step 4 API flow passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
