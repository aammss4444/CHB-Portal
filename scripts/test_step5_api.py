from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID
import httpx
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from app.db.session import AsyncSessionLocal
from app.models.advertisement import Advertisement, AdvertisementStatus
from app.models.application import Application, ApplicationStatus

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
    return body.get("data", body)

async def get_test_data() -> tuple[UUID, UUID, int, str]:
    async with AsyncSessionLocal() as db:
        # Get ad with submitted applications
        stmt = (
            select(Advertisement)
            .options(selectinload(Advertisement.assessment))
            .where(Advertisement.status == AdvertisementStatus.PUBLISHED.value)
            .order_by(Advertisement.created_at.desc())
        )
        ad = (await db.execute(stmt)).scalars().first()
        if not ad:
            raise RuntimeError("No published advertisement found. Run Step 4 test first.")
        
        # Check if there is a submitted or under_review application for this ad
        app_stmt = select(Application).where(
            and_(
                Application.advertisement_id == ad.id, 
                Application.status.in_([ApplicationStatus.SUBMITTED.value, ApplicationStatus.UNDER_REVIEW.value])
            )
        )
        app = (await db.execute(app_stmt)).scalars().first()
        if not app:
             raise RuntimeError(f"No active application found for advertisement {ad.id}. Run Step 4 test first.")
             
        level = "UG"
        from app.models.institution import Course
        course = (await db.execute(select(Course).where(Course.id == ad.course_id))).scalars().first()
        level = course.level if course else "UG"

        return ad.id, app.id, ad.course_id, level

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

async def amain():
    ad_id, app_id, course_id, level = await get_test_data()
    
    with httpx.Client(timeout=40.0) as client:
        admin_token = login(client, "s.admin@gmail.com", "1234")
        principal_token = login(client, "principal@gmail.com", "1234")
        
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        principal_headers = {"Authorization": f"Bearer {principal_token}"}

        # 1) Check weights resolution (Default)
        print("1) GET /scoring-weights/resolve (Principal)")
        resolve_data = expect_envelope(client.get(
            f"{BASE_URL}/api/scoring-weights/resolve",
            params={"course_id": course_id, "level": level, "advertisement_id": str(ad_id)},
            headers=principal_headers
        ))
        print(f"   Matched Priority: {resolve_data['matched_priority']}")
        
        # 2) Admin creates a course-specific config
        print("2) POST /scoring-weights (Admin)")
        try:
            expect_envelope(client.post(
                f"{BASE_URL}/api/scoring-weights",
                headers=admin_headers,
                json={
                    "config_name": f"TEST_CONFIG_{course_id}",
                    "course_id": course_id,
                    "level": level,
                    "qualification_weight": 40,
                    "experience_weight": 20,
                    "interview_weight": 30,
                    "publication_weight": 5,
                    "reservation_weight": 5,
                    "effective_from": str(date.today())
                }
            ))
        except ApiFailure as e:
            if e.code == "WEIGHT_CONFIG_OVERLAP":
                print("   Config already exists, continuing...")
            else: raise

        # 3) Create Selection Round
        print("3) POST /selection/rounds (Principal)")
        try:
            round_data = expect_envelope(client.post(
                f"{BASE_URL}/api/selection/rounds",
                headers=principal_headers,
                json={
                    "advertisement_id": str(ad_id),
                    "round_type": "INTERVIEW",
                    "scheduled_date": str(date.today() + timedelta(days=1))
                }
            ))
            round_id = round_data["round_id"]
        except ApiFailure as e:
            if e.code == "ROUND_ALREADY_EXISTS":
                print("   Round already exists, fetching ID...")
                async with AsyncSessionLocal() as db:
                    from app.models.selection_round import SelectionRound
                    r_stmt = select(SelectionRound).where(
                        and_(SelectionRound.advertisement_id == ad_id, SelectionRound.round_type == "INTERVIEW")
                    )
                    r_obj = (await db.execute(r_stmt)).scalars().first()
                    round_id = r_obj.id
            else: raise

        # 4) Shortlist
        print("4) POST /selection/rounds/{id}/shortlist")
        expect_envelope(client.post(
            f"{BASE_URL}/api/selection/rounds/{round_id}/shortlist",
            headers=principal_headers,
            json={
                "application_ids": [str(app_id)],
                "remarks": "Test shortlist"
            }
        ))

        # 5) Mark Attendance (SKIPPED TO VERIFY BYPASS)
        print("5) POST /selection/rounds/{id}/attendance (SKIPPED)")
        # expect_envelope(client.post(
        #     f"{BASE_URL}/api/selection/rounds/{round_id}/attendance",
        #     headers=principal_headers,
        #     json={
        #         "attendance": [
        #             {"application_id": str(app_id), "is_present": True}
        #         ]
        #     }
        # ))

        # 6) Enter Marks for ALL present candidates
        print("6) POST /selection/marks (All present candidates)")
        async with AsyncSessionLocal() as db:
            from app.models.shortlisted_candidate import ShortlistedCandidate
            from app.models.application import Application
            sc_stmt = select(ShortlistedCandidate).where(
                ShortlistedCandidate.round_id == round_id
            )
            scs = (await db.execute(sc_stmt)).scalars().all()
            
            for sc in scs:
                app_obj = (await db.execute(select(Application).where(Application.id == sc.application_id))).scalars().first()
                print(f"   Entering marks for App: {sc.application_id}")
                try:
                    expect_envelope(client.post(
                        f"{BASE_URL}/api/selection/marks",
                        headers=principal_headers,
                        json={
                            "round_id": str(round_id),
                            "application_id": str(sc.application_id),
                            "candidate_id": str(sc.candidate_id),
                            "institution_id": app_obj.institution_id,
                            "subject_knowledge": 85,
                            "teaching_aptitude": 90,
                            "communication_skills": 80,
                            "overall_impression": 88
                        }
                    ))
                except ApiFailure as e:
                    if e.code in ["MARKS_ALREADY_ENTERED", "INTEGRITY_ERROR"]:
                        print(f"   Marks already exist or integrity error ({e.code}) for {sc.application_id}")
                    else: raise

        # 7) Generate Ranking
        print("7) POST /selection/rounds/{id}/rank")
        ranked_list = expect_envelope(client.post(
            f"{BASE_URL}/api/selection/rounds/{round_id}/rank",
            headers=principal_headers
        ))
        print(f"   Ranked count: {len(ranked_list)}")

        # 8) Confirm Selection
        print("8) POST /selection/rounds/{id}/confirm")
        expect_envelope(client.post(
            f"{BASE_URL}/api/selection/rounds/{round_id}/confirm",
            headers=principal_headers,
            json={"remarks": "Confirmed for Step 5 test"}
        ))

        # 9) View Final Results
        print("9) GET /results/{ad_id}")
        final_results = expect_envelope(client.get(
            f"{BASE_URL}/api/selection/results/{ad_id}",
            headers=principal_headers
        ))
        print(f"   Selected count: {len(final_results['SELECTED'])}")

        print("\nOK: Step 5 Selection Process test passed!")

if __name__ == "__main__":
    asyncio.run(amain())
