
import json
import uuid

def create_item(name, method, path, body=None, description="", is_bearer=True):
    item = {
        "name": name,
        "request": {
            "method": method,
            "header": [
                {"key": "Accept", "value": "application/json"}
            ],
            "url": {
                "raw": "{{baseUrl}}" + "/".join([""] + path),
                "host": ["{{baseUrl}}"],
                "path": path
            },
            "description": description
        },
        "response": []
    }
    
    if method in ["POST", "PUT", "PATCH"]:
        item["request"]["header"].append({"key": "Content-Type", "value": "application/json"})
        if body:
            item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(body, indent=2),
                "options": {"raw": {"language": "json"}}
            }
            
    if is_bearer:
        item["request"]["auth"] = {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{accessToken}}", "type": "string"}]
        }
        
    return item

def main():
    file_path = r"d:\Projects\CHB Portal\CHB_Portal.postman_collection.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Step 1: Requirements
    step1_items = [
        create_item("List Institutions", "GET", ["api", "requirements", "institutions"]),
        create_item("Create Institution", "POST", ["api", "requirements", "institutions"], {
            "name": "Example Institute",
            "code": "INST001",
            "district": "Pune",
            "type": "GOVERNMENT",
            "branches": [{"name": "Computer Science", "level": "UG"}]
        }),
        create_item("Update Institution", "PATCH", ["api", "requirements", "institutions", "1"], {"name": "Updated Name"}),
        create_item("Update Branch", "PATCH", ["api", "requirements", "branches", "1"], {"level": "PG"}),
        create_item("List Norms", "GET", ["api", "requirements", "norms"]),
        create_item("Create Norm", "POST", ["api", "requirements", "norms"], {
            "academic_year": "2026-2027",
            "course_level": "UG",
            "category": "student_faculty_ratio",
            "faculty_student_ratio": 20.0,
            "min_qualification": "PhD",
            "max_daily_lectures": 6,
            "credit_to_hour_ratio": 1.0
        }),
        create_item("Update Norm", "PATCH", ["api", "requirements", "norms", "1"], {"faculty_student_ratio": 15.0}),
        create_item("Define Intake", "POST", ["api", "requirements", "intake"], {
            "institution_id": 1,
            "branch_name": "Computer Science",
            "academic_year": "2026-2027",
            "approved_seats": 60,
            "actual_admitted": 55
        }),
        create_item("Generate Requirements", "POST", ["api", "requirements", "generate"], {
            "intake_id": "00000000-0000-0000-0000-000000000000"
        }),
        create_item("Validate Requirements (AI)", "POST", ["api", "requirements", "validate"], {
            "intake_id": "00000000-0000-0000-0000-000000000000"
        }),
        create_item("AI Query Database", "GET", ["api", "requirements", "ai-query"], description="Query: List branches with high student ratio")
    ]
    
    # Step 2: Vacancy Identification
    step2_items = [
        create_item("Add Faculty", "POST", ["api", "vacancies", "faculty"], {
            "institution_id": 1,
            "branch_id": 1,
            "name": "John Doe",
            "designation": "Assistant Professor",
            "specialization": "AI",
            "employment_type": "PERMANENT",
            "joining_date": "2020-01-01",
            "academic_year": "2026-2027"
        }),
        create_item("Update Faculty", "PUT", ["api", "vacancies", "faculty", "00000000-0000-0000-0000-000000000000"], {
            "designation": "Associate Professor"
        }),
        create_item("Get Faculty List", "GET", ["api", "vacancies", "faculty"]), # Needs query params: institution_id, branch_id, academic_year
        create_item("Delete Faculty", "DELETE", ["api", "vacancies", "faculty", "00000000-0000-0000-0000-000000000000"]), # Needs query param: reason
        create_item("Suggest Vacancy (AI)", "POST", ["api", "vacancies", "suggest"], {
            "institution_id": 1,
            "branch_id": 1,
            "academic_year": "2026-2027",
            "required_faculty": 10,
            "existing_faculty_count": 7
        }),
        create_item("Get Assessment", "GET", ["api", "vacancies", "assessment"]), # Needs query params
        create_item("Confirm Vacancy", "POST", ["api", "vacancies", "confirm"], {
            "suggested_vacancy": 3,
            "justification": "Increased workload"
        }), # Path needs params: institution_id, branch_id, academic_year as query params or path?
        create_item("Acknowledge Anomaly", "POST", ["api", "vacancies", "anomalies", "00000000-0000-0000-0000-000000000000", "acknowledge"], {
            "resolution_remarks": "Verified manual count"
        })
    ]
    
    # Update "Get Faculty List" with query params
    step2_items[2]["request"]["url"]["query"] = [
        {"key": "institution_id", "value": "1"},
        {"key": "branch_id", "value": "1"},
        {"key": "academic_year", "value": "2026-2027"}
    ]
    
    # Update "Delete Faculty" with query params
    step2_items[3]["request"]["url"]["query"] = [
        {"key": "reason", "value": "Retirement"}
    ]

    # Update "Confirm Vacancy" - router says institution_id, branch_id, academic_year as query params
    step2_items[6]["request"]["url"]["query"] = [
        {"key": "institution_id", "value": "1"},
        {"key": "branch_id", "value": "1"},
        {"key": "academic_year", "value": "2026-2027"}
    ]

    # Update "Get Assessment" with query params
    step2_items[5]["request"]["url"]["query"] = [
        {"key": "institution_id", "value": "1"},
        {"key": "branch_id", "value": "1"},
        {"key": "academic_year", "value": "2026-2027"}
    ]

    # Add "ai-query" query param
    step1_items[-1]["request"]["url"]["query"] = [
        {"key": "query", "value": "List all branches in Pune"}
    ]

    step1_folder = {
        "name": "Requirements (Step 1)",
        "item": step1_items
    }
    
    step2_folder = {
        "name": "Vacancy Identification (Step 2)",
        "item": step2_items
    }
    
    # Insert at the beginning of 'api' item list
    api_item = next((item for item in data["item"] if item["name"] == "api"), None)
    if api_item:
        # Check if already exists to avoid duplicates
        existing_names = [item["name"] for item in api_item["item"]]
        if "Requirements (Step 1)" not in existing_names:
            api_item["item"].insert(0, step1_folder)
        if "Vacancy Identification (Step 2)" not in existing_names:
            # Insert after Step 1
            idx = 1 if "Requirements (Step 1)" in existing_names or step1_folder in api_item["item"] else 0
            api_item["item"].insert(idx, step2_folder)
            
        # Re-sort if necessary to ensure Step 1, 2, 3...
        # For now, just prepending is fine as Step 3 was there.
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print("Postman collection updated successfully.")

if __name__ == "__main__":
    main()
