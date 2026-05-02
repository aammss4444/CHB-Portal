# CHB Portal Step 1 API Contract (Latest)

Base path: `/api/requirements`

Auth: Bearer JWT required on all endpoints below.

## 1) Institutions and Courses

### POST `/institutions`
Role: `ADMIN`

Request:
```json
{
  "name": "Govt College Pune",
  "code": "DTE001",
  "district": "Pune",
  "type": "Government",
  "courses": [
    { "name": "Computer Engineering", "level": "UG" }
  ]
}
```

### GET `/institutions`
Role: Authenticated

### PATCH `/institutions/{institution_id}`
Role: `ADMIN`

### PATCH `/courses/{course_id}`
Role: `ADMIN`

## 2) Norm Discovery and Configuration

### GET `/norms/types`
Role: `ADMIN`, `PRINCIPAL`

Response:
```json
{ "types": ["COURSE_WISE", "GENERAL"] }
```

### GET `/norms/courses`
Role: `ADMIN`, `PRINCIPAL`

Response:
```json
[
  "Engineering Diploma",
  "Engineering Degree",
  "Pharmacy",
  "HMCT",
  "Applied Sciences"
]
```

### POST `/norms`
Role: `ADMIN`

Validation:
- If `norm_type` is `COURSE_WISE`, `course_category` is mandatory.

Request:
```json
{
  "academic_year": "2026-27",
  "norm_type": "COURSE_WISE",
  "course_category": "Engineering Degree",
  "course_level": "UG",
  "category": "student_faculty_ratio",
  "min_qualification": "M.E/M.Tech",
  "grade_requirement": "First Class",
  "faculty_student_ratio": 20,
  "max_age": 38,
  "workload_hours_per_week": 18,

  "max_daily_lectures": 6,
  "credit_to_hour_ratio": 1.0
}
```

### GET `/norms`
Role: `ADMIN`, `PRINCIPAL`

### PATCH `/norms/{norm_id}`
Role: `ADMIN`

## 3) Intake Definition

### POST `/intake`
Role: `ADMIN`

Request:
```json
{
  "institution_id": 1,
  "course_name": "Computer Engineering",
  "academic_year": "2026-2027",
  "approved_seats": 120,
  "actual_admitted": 110
}
```

## 4) Requirement Generation and Validation

### POST `/generate`
Role: `ADMIN`

Request:
```json
{ "intake_id": 10 }
```

Norm resolution priority used by backend:
1. `COURSE_WISE` by `course_category` + `academic_year`
2. `GENERAL` by `academic_year`
3. Legacy fallback norm

Calculation:
- `required = ceil(max(approved_seats, actual_admitted) / faculty_student_ratio)`

Response includes both legacy and new fields:
```json
{
  "id": 21,
  "intake_id": 10,
  "computed_required_count": 6,
  "required_faculty": 6,
  "formula_breakdown": {
    "base_used": 120,
    "norm_ratio_applied": 20,
    "calculation": "ceil(120 / 20)",
    "norm_type": "COURSE_WISE",
    "course_category": "Engineering Degree"
  },
  "norm_used": {
    "type": "COURSE_WISE",
    "course": "Engineering Degree",
    "qualification": "M.E/M.Tech",
    "grade": "First Class",
    "ratio": 20
  },
  "created_at": "2026-04-28T12:00:00Z",
  "anomalies": []
}
```

### POST `/validate`
Role: `ADMIN`

Request:
```json
{ "intake_id": 10 }
```

## 5) Legacy / Utility Step 1 Endpoints

### GET `/assessments?institution_id={id}&course_id={id}&academic_year={yyyy-yyyy}`
Role: `ADMIN`

Backward-compatible alias for vacancy assessment consumers.

### GET `/ai-query?query={text}`
Role: `ADMIN`

Experimental natural-language query endpoint for Step 1 data.

## Notes for Frontend

- For norm setup UI, always call in this order:
  1. `GET /norms/types`
  2. If `COURSE_WISE`, call `GET /norms/courses`
  3. Submit `POST /norms`
- `POST /generate` now returns `norm_used` and `required_faculty` in addition to legacy response fields.
- Existing endpoints and existing response fields remain backward compatible.
