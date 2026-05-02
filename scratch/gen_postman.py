"""
Generate a properly arranged Postman Collection v2.1 from FastAPI OpenAPI spec.

Structure:
  - Folders ordered by workflow step (Auth -> Step 1 -> ... -> Step 10)
  - Within each step, sub-folders: Core APIs | AI APIs
  - Every request has a meaningful example body (not generic placeholders)
  - Auto-token script on Login
"""
import sys, os, json, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app

openapi = app.openapi()
paths = openapi.get("paths", {})

BASE_URL = "{{baseUrl}}"

# ---- Ordering ----
TAG_ORDER = {
    "Authentication":                        0,
    "Requirements (Step 1)":                 1,
    "Vacancy Identification (Step 2)":       2,
    "Advertisement Creation (Step 3)":       3,
    "Candidate Profile (Step 4)":            4,
    "Application Management (Step 4)":       5,
    "Scoring Weight Configuration (Step 5)": 6,
    "Selection Process (Step 5)":            7,
    "Appointment Management (Step 6)":       8,
    "Attendance & Work Log (Step 7)":        9,
    "Billing (Step 8)":                      10,
    "Payments (Step 9)":                     11,
    "Audit & Compliance AI (Step 9)":        12,
    "AI Helpdesk (Step 10)":                 13,
    "Untagged":                              99,
}

# Paths that are AI endpoints (used for sub-folder grouping)
AI_PATH_MARKERS = [
    "/ai-", "/analyze-ai", "/generate-ai", "/ai-query",
    "/ai-analysis", "/ai-snapshot", "/ai-validate",
    "/ai-readiness", "/ai-monitor", "/ai-check",
    "/ai-summary", "/ai-report", "/helpdesk/query",
]

def _is_ai_path(path):
    return any(marker in path for marker in AI_PATH_MARKERS)

def _sort_key(tag):
    return TAG_ORDER.get(tag, 50)

def make_id():
    return str(uuid.uuid4())

# ---- Custom example bodies for key endpoints ----
CUSTOM_BODIES = {
    "POST /api/auth/login": {
        "username": "admin@chb.gov.in",
        "password": "Admin@123"
    },
    "POST /api/auth/register": {
        "email": "principal@college.edu",
        "password": "Secure@456",
        "full_name": "Dr. Rajesh Kumar",
        "role": "PRINCIPAL",
        "institution_id": 1
    },
    "POST /api/auth/candidate/register": {
        "email": "candidate@gmail.com",
        "password": "Candidate@789",
        "full_name": "Priya Sharma",
        "phone_number": "9876543210"
    },
    "POST /api/auth/forgot-password": {
        "email": "admin@chb.gov.in"
    },
    "POST /api/auth/reset-password": {
        "token": "<reset-token-from-email>",
        "new_password": "NewSecure@123"
    },
    "POST /api/requirements/institutions": {
        "name": "Government Polytechnic, Pune",
        "code": "GP-PUNE-001",
        "district": "Pune",
        "type": "GOVERNMENT",
        "courses": [
            {"name": "Computer Engineering", "level": "DIPLOMA"},
            {"name": "Mechanical Engineering", "level": "DIPLOMA"}
        ]
    },
    "PATCH /api/requirements/institutions/{institution_id}": {
        "name": "Government Polytechnic, Mumbai",
        "district": "Mumbai"
    },
    "POST /api/requirements/norms": {
        "institution_id": 1,
        "academic_year": "2026-2027",
        "norm_type": "DTE_DEFAULT",
        "course_category": "ENGINEERING_DIPLOMA",
        "faculty_student_ratio": 20.0,
        "min_qualification": "B.E./B.Tech with 55% marks",
        "grade_requirement": "First Class",
        "max_age": 38,
        "workload_hours_per_week": 18
    },
    "PATCH /api/requirements/norms/{norm_id}": {
        "faculty_student_ratio": 15.0,
        "max_age": 40
    },
    "POST /api/requirements/intake": {
        "course_id": 1,
        "academic_year": "2026-2027",
        "approved_seats": 60,
        "actual_admitted": 55
    },
    "POST /api/requirements/course-setup": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027",
        "approved_seats": 60,
        "actual_admitted": 55,
        "faculty_student_ratio": 20.0,
        "norm_type": "DTE_DEFAULT",
        "min_qualification": "B.E./B.Tech",
        "grade_requirement": "First Class",
        "max_age": 38,
        "workload_hours_per_week": 18
    },
    "POST /api/requirements/generate": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027"
    },
    "POST /api/requirements/validate": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027"
    },
    "POST /api/vacancies/faculty": {
        "institution_id": 1,
        "course_id": 1,
        "name": "Dr. Anil Deshmukh",
        "designation": "Lecturer",
        "specialization": "Computer Science",
        "employment_type": "CHB",
        "qualification": "M.Tech Computer Science",
        "joining_date": "2024-07-01",
        "date_of_birth": "1988-05-15",
        "academic_year": "2026-2027"
    },
    "PUT /api/vacancies/faculty/{faculty_id}": {
        "designation": "Senior Lecturer",
        "specialization": "Artificial Intelligence"
    },
    "POST /api/vacancies/suggest": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027"
    },
    "POST /api/vacancies/confirm": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027",
        "confirmed_count": 3,
        "justification": "Based on DTE norms and current workload analysis"
    },
    "POST /api/vacancies/ai-analysis": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027"
    },
    "POST /api/vacancies/anomalies/{anomaly_id}/acknowledge": {
        "resolution_remarks": "Verified with manual faculty count records"
    },
    "POST /api/advertisements/generate": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027",
        "vacancy_count": 3,
        "designation": "Lecturer",
        "qualification_required": "B.E./B.Tech with First Class",
        "last_date": "2026-06-30"
    },
    "POST /api/advertisements/generate-ai": {
        "institution_id": 1,
        "course_id": 1,
        "academic_year": "2026-2027",
        "vacancy_count": 3,
        "designation": "Lecturer",
        "qualification_required": "B.E./B.Tech with First Class",
        "last_date": "2026-06-30"
    },
    "POST /api/advertisements/{advertisement_id}/approve": {
        "action": "APPROVE",
        "remarks": "Verified all details"
    },
    "POST /api/advertisements/{advertisement_id}/submit": {
        "remarks": "Ready for review"
    },
    "POST /api/candidates/profile": {
        "full_name": "Priya Sharma",
        "phone": "9876543210",
        "date_of_birth": "1995-03-15",
        "gender": "FEMALE",
        "category": "OPEN",
        "address": "123 MG Road, Pune, Maharashtra"
    },
    "POST /api/candidates/qualifications": [
        {
            "degree": "M.Tech",
            "specialization": "Computer Science",
            "university": "Pune University",
            "year_of_passing": 2020,
            "percentage": 78.5,
            "grade": "First Class with Distinction"
        }
    ],
    "POST /api/candidates/experience": [
        {
            "organization": "ABC Polytechnic",
            "designation": "Lecturer",
            "from_date": "2020-08-01",
            "to_date": "2025-05-31",
            "experience_type": "TEACHING",
            "description": "Teaching Computer Science subjects"
        }
    ],
    "POST /api/applications": {
        "advertisement_id": "00000000-0000-0000-0000-000000000000",
        "cover_letter": "I am interested in the CHB Lecturer position at your institution."
    },
    "POST /api/scoring-weights": {
        "academic_year": "2026-2027",
        "qualification_weight": 30.0,
        "experience_weight": 25.0,
        "interview_weight": 35.0,
        "demo_weight": 10.0
    },
    "POST /api/scoring-weights/advertisement/{advertisement_id}": {
        "qualification_weight": 25.0,
        "experience_weight": 30.0,
        "interview_weight": 35.0,
        "demo_weight": 10.0
    },
    "POST /api/selection/rounds": {
        "advertisement_id": "00000000-0000-0000-0000-000000000000",
        "round_type": "INTERVIEW",
        "scheduled_date": "2026-07-15",
        "venue": "Government Polytechnic Pune, Seminar Hall"
    },
    "POST /api/selection/marks": {
        "round_id": "00000000-0000-0000-0000-000000000000",
        "candidate_id": "00000000-0000-0000-0000-000000000000",
        "marks_obtained": 85.0,
        "max_marks": 100.0,
        "remarks": "Excellent technical knowledge"
    },
    "POST /api/appointments/generate": {
        "selection_result_id": "00000000-0000-0000-0000-000000000000",
        "joining_date": "2026-08-01",
        "designation": "CHB Lecturer",
        "department": "Computer Engineering"
    },
    "POST /api/appointments/{appointment_id}/approve": {
        "action": "APPROVE",
        "remarks": "All documents verified"
    },
    "POST /api/appointments/{appointment_id}/respond": {
        "action": "ACCEPT",
        "remarks": "I accept the appointment"
    },
    "POST /api/attendance/timetable": {
        "faculty_credential_id": "00000000-0000-0000-0000-000000000000",
        "institution_id": 1,
        "academic_year": "2026-2027",
        "slots": [
            {"day": "MONDAY", "start_time": "09:00", "end_time": "10:00", "subject": "Data Structures", "lecture_type": "THEORY"},
            {"day": "MONDAY", "start_time": "10:00", "end_time": "11:00", "subject": "DBMS Lab", "lecture_type": "PRACTICAL"}
        ]
    },
    "POST /api/attendance/logs": {
        "faculty_credential_id": "00000000-0000-0000-0000-000000000000",
        "timetable_slot_id": "00000000-0000-0000-0000-000000000000",
        "log_date": "2026-08-15",
        "lecture_type": "THEORY",
        "topic_covered": "Introduction to Linked Lists",
        "hours": 1
    },
    "POST /api/attendance/calendar": {
        "institution_id": 1,
        "academic_year": "2026-2027",
        "date": "2026-08-15",
        "day_type": "WORKING",
        "remarks": "Regular working day"
    },
    "POST /api/billing/rates": {
        "institution_id": 1,
        "academic_year": "2026-2027",
        "rates": [
            {"designation": "LECTURER", "lecture_type": "THEORY", "rate_per_hour": 500.00},
            {"designation": "LECTURER", "lecture_type": "PRACTICAL", "rate_per_hour": 250.00}
        ]
    },
    "POST /api/billing/generate": {
        "faculty_credential_id": "00000000-0000-0000-0000-000000000000",
        "institution_id": 1,
        "academic_year": "2026-2027",
        "month": 8,
        "year": 2026
    },
    "POST /api/billing/generate/bulk": {
        "institution_id": 1,
        "academic_year": "2026-2027",
        "month": 8,
        "year": 2026
    },
    "POST /api/billing/bills/{bill_id}/approve": {
        "action": "APPROVE",
        "remarks": "All entries verified against attendance"
    },
    "POST /api/payments/initiate/{bill_id}": {
        "payment_mode": "NEFT",
        "remarks": "Monthly CHB payment"
    },
    "POST /api/payments/process/{payment_id}": {
        "transaction_reference": "NEFT-REF-20260815-001",
        "processed_date": "2026-08-20"
    },
    "POST /api/helpdesk/query": {
        "query": "How do I generate a bill for August 2026?",
        "context": "billing"
    },
}

# ---- Schema resolution helpers ----
def resolve_ref(ref_str):
    parts = ref_str.lstrip("#/").split("/")
    node = openapi
    for p in parts:
        node = node.get(p, {})
    return node

def schema_to_example(schema, depth=0):
    if depth > 5:
        return {}
    if "$ref" in schema:
        schema = resolve_ref(schema["$ref"])
    if "allOf" in schema:
        merged = {}
        for sub in schema["allOf"]:
            merged.update(schema_to_example(sub, depth + 1) or {})
        return merged
    for key in ("anyOf", "oneOf"):
        if key in schema:
            for option in schema[key]:
                if option.get("type") != "null":
                    return schema_to_example(option, depth + 1)
            return None
    t = schema.get("type", "object")
    if t == "object":
        return {n: schema_to_example(s, depth + 1) for n, s in schema.get("properties", {}).items()}
    if t == "array":
        return [schema_to_example(schema.get("items", {}), depth + 1)]
    if t == "string":
        fmt = schema.get("format", "")
        if fmt == "email": return "user@example.com"
        if fmt == "date-time": return "2026-01-01T00:00:00Z"
        if fmt == "date": return "2026-01-01"
        if fmt == "uuid": return "00000000-0000-0000-0000-000000000000"
        if schema.get("enum"): return schema["enum"][0]
        if schema.get("default") is not None: return schema["default"]
        return ""
    if t == "integer": return schema.get("default", 0)
    if t == "number": return schema.get("default", 0.0)
    if t == "boolean": return schema.get("default", False)
    return None

def get_body(operation, method, path):
    rb = operation.get("requestBody", {}).get("content", {})
    
    # Prioritize form-data if the endpoint expects it (e.g. login)
    form_ct = rb.get("application/x-www-form-urlencoded", {}).get("schema", {})
    if form_ct:
        return "form", form_ct

    # Check custom bodies for JSON
    key = f"{method.upper()} {path}"
    if key in CUSTOM_BODIES:
        return "json", CUSTOM_BODIES[key]

    json_ct = rb.get("application/json", {}).get("schema", {})
    if json_ct:
        return "json", schema_to_example(json_ct)
    
    return None, None

def build_form_params(schema, method, path):
    if "$ref" in schema:
        schema = resolve_ref(schema["$ref"])
    params = []
    
    custom_data = CUSTOM_BODIES.get(f"{method.upper()} {path}", {})
    
    for name, ps in schema.get("properties", {}).items():
        # Use custom value if available, else generate example
        val = custom_data.get(name)
        if val is None:
            val = schema_to_example(ps)
            
        params.append({
            "key": name,
            "value": str(val or ""),
            "description": ps.get("description", ""),
        })
    return params

def needs_auth(operation):
    sec = operation.get("security", openapi.get("security", []))
    return len(sec) > 0

# ---- Build Postman item ----
def build_item(method, path, operation):
    summary = operation.get("summary", "") or operation.get("operationId", path)
    description = operation.get("description", "")

    # URL
    parts = [p for p in path.strip("/").split("/") if p]
    url_path, variables = [], []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            var = part[1:-1]
            url_path.append(f":{var}")
            variables.append({"key": var, "value": "", "description": f"ID of the {var.replace('_', ' ')}"})
        else:
            url_path.append(part)

    query_params = []
    for param in operation.get("parameters", []):
        if param.get("in") == "query":
            val = ""
            if param["name"] == "academic_year":
                val = "2026-2027"
            elif param["name"] == "institution_id":
                val = "1"
                
            query_params.append({
                "key": param["name"],
                "value": val,
                "disabled": not param.get("required", False),
                "description": param.get("description", ""),
            })

    url = {"raw": BASE_URL + "/" + "/".join(url_path), "path": url_path, "host": [BASE_URL], "query": query_params, "variable": variables}

    headers = [{"key": "Accept", "value": "application/json"}]

    body_type, body_data = get_body(operation, method, path)
    body_obj = {}
    if body_type == "json" and body_data is not None:
        headers.insert(0, {"key": "Content-Type", "value": "application/json"})
        body_obj = {
            "mode": "raw",
            "raw": json.dumps(body_data, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    elif body_type == "form":
        headers.insert(0, {"key": "Content-Type", "value": "application/x-www-form-urlencoded"})
        body_obj = {"mode": "urlencoded", "urlencoded": build_form_params(body_data, method, path)}

    auth = None
    if needs_auth(operation):
        auth = {"type": "bearer", "bearer": [{"key": "token", "value": "{{accessToken}}", "type": "string"}]}

    request = {
        "name": summary,
        "description": description,
        "url": url,
        "header": headers,
        "method": method.upper(),
        "auth": auth,
    }
    if body_obj:
        request["body"] = body_obj

    item = {
        "id": make_id(),
        "name": summary,
        "request": request,
        "response": [],
        "event": [],
        "protocolProfileBehavior": {"disableBodyPruning": True},
    }

    # Auto-token script for login
    if path == "/api/auth/login" and method.lower() == "post":
        item["event"].append({
            "listen": "test",
            "script": {
                "type": "text/javascript",
                "exec": [
                    "var jsonData = pm.response.json();",
                    "if (jsonData && jsonData.access_token) {",
                    "    pm.collectionVariables.set('accessToken', jsonData.access_token);",
                    "    console.log('Access token saved!');",
                    "}",
                ],
            },
        })

    return item

# ---- Grouping ----
def group_by_tag(all_paths):
    groups = {}
    for path, methods in all_paths.items():
        for method, operation in methods.items():
            tag = (operation.get("tags") or ["Untagged"])[0]
            groups.setdefault(tag, []).append((method, path, operation))
    return groups

def build_folder_for_tag(tag, operations):
    method_weight = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}

    core_ops = [(m, p, op) for m, p, op in operations if not _is_ai_path(p)]
    ai_ops = [(m, p, op) for m, p, op in operations if _is_ai_path(p)]

    core_ops.sort(key=lambda t: (t[1], method_weight.get(t[0].upper(), 5)))
    ai_ops.sort(key=lambda t: (t[1], method_weight.get(t[0].upper(), 5)))

    items = []

    # If there are both core and AI ops, create sub-folders
    if core_ops and ai_ops:
        core_items = [build_item(m, p, op) for m, p, op in core_ops]
        ai_items = [build_item(m, p, op) for m, p, op in ai_ops]
        items.append({"name": "Core APIs", "description": f"Standard CRUD endpoints for {tag}", "item": core_items})
        items.append({"name": "AI APIs", "description": f"AI-powered intelligence endpoints for {tag}", "item": ai_items})
    else:
        all_ops = core_ops + ai_ops
        all_ops.sort(key=lambda t: (t[1], method_weight.get(t[0].upper(), 5)))
        items = [build_item(m, p, op) for m, p, op in all_ops]

    return {"name": tag, "description": f"All endpoints for {tag}", "item": items}

# ---- Main ----
def main():
    groups = group_by_tag(paths)

    folders = []
    for tag in sorted(groups.keys(), key=_sort_key):
        if tag == "Untagged":
            continue
        folders.append(build_folder_for_tag(tag, groups[tag]))

    if "Untagged" in groups:
        folders.append(build_folder_for_tag("General", groups["Untagged"]))

    collection = {
        "info": {
            "_postman_id": make_id(),
            "name": "CHB Portal - Complete API Collection",
            "description": (
                "Complete API collection for the Clock Hour Basis (CHB) Portal Backend.\\n\\n"
                "**How to use:**\\n"
                "1. Set the `baseUrl` variable to your server (default: http://localhost:8000)\\n"
                "2. Call 'Login For Access Token' first - it auto-saves the token\\n"
                "3. All other requests use the saved token automatically\\n\\n"
                "**Structure:**\\n"
                "- Each step folder contains 'Core APIs' and 'AI APIs' sub-folders\\n"
                "- Steps are ordered from Authentication through Step 10"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": folders,
        "variable": [
            {"key": "baseUrl", "value": "http://localhost:8000", "type": "string"},
            {"key": "accessToken", "value": "", "type": "string"},
        ],
        "event": [
            {"listen": "prerequest", "script": {"type": "text/javascript", "exec": [""]}},
            {"listen": "test", "script": {"type": "text/javascript", "exec": [""]}},
        ],
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "CHB_Portal.postman_collection.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)

    print(f"[OK] Postman collection generated: {os.path.abspath(out_path)}")
    total = 0
    for fd in folders:
        sub_count = 0
        for item in fd["item"]:
            if "item" in item:
                sub_count += len(item["item"])
            else:
                sub_count += 1
        total += sub_count
        print(f"  {fd['name']} ({sub_count} endpoints)")
        for item in fd["item"]:
            if "item" in item:
                print(f"    [{item['name']}] ({len(item['item'])} endpoints)")
                for sub in item["item"]:
                    m = sub["request"]["method"]
                    print(f"      [{m:6s}] {sub['name']}")
            else:
                m = item["request"]["method"]
                print(f"    [{m:6s}] {item['name']}")
    print(f"\nTotal: {total} endpoints")


if __name__ == "__main__":
    main()
