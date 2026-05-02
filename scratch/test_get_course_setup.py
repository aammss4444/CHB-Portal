import asyncio
from fastapi.testclient import TestClient
from app.main import app

def test_get_setup():
    client = TestClient(app)
    # Login to get token
    response = client.post("/api/auth/login", data={"username": "admin@chb.gov", "password": "Admin@123"})
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} - {response.text}")
        return
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, setup a course (assuming institution 1, course 1 exist, which they do from previous tests)
    setup_data = {
        "institution_id": 1,
        "course_name": "Computer Engineering",
        "academic_year": "2026-2027",
        "approved_seats": 60,
        "actual_admitted": 55,
        "faculty_student_ratio": 20.0,
        "min_qualification": "B.E./B.Tech",
        "grade_requirement": "First Class",
        "norm_type": "COURSE_WISE",
        "max_age": 38,
        "workload_hours_per_week": 18
    }
    res = client.post("/api/requirements/course-setup", json=setup_data, headers=headers)
    print(f"POST /course-setup: {res.status_code}")
    if res.status_code not in (200, 201):
        print(res.text)
        return

    # Now get it
    course_id = res.json()["intake"]["course_id"]
    res_get = client.get(f"/api/requirements/course-setup/{course_id}?academic_year=2026-2027", headers=headers)
    print(f"GET /course-setup/{course_id}: {res_get.status_code}")
    if res_get.status_code == 200:
        print(res_get.json())
    else:
        print(res_get.text)

if __name__ == "__main__":
    test_get_setup()
