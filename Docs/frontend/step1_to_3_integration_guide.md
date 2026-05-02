# Frontend Integration Guide: Step 1 (Norms) & Step 2 (Vacancy)

> **Status:** Final Production Version (AI-Centric & SRS Aligned)  
> **Scope:** Faculty Requirement Generation (Step 1) and Vacancy Identification (Step 2).

---

## 1. AI Business Objectives (SRS 7.6.3)

### 1.1 Faculty Requirement Calculator (AI-Assisted)
The system uses AI-assisted rule validation to:
*   Calculate faculty requirements based on intake, course norms, and faculty-student ratios.
*   Compare current requirements with historical utilization data.
*   Flag abnormal variations for review.
*   **Outcome**: AI generates a **“Suggested Requirement Summary”**, while final approval remains with the Directorate.

### 1.2 Faculty Allocation & Vacancy Identification
AI assists by:
*   Analyzing existing faculty strength and workload.
*   Identifying optimal CHB vacancy distribution.
*   Highlighting underutilized or overloaded courses.
*   **Outcome**: The system presents **AI-recommended vacancy lists with justification**, enabling faster and more accurate approvals.

---

## 2. Step 1: Norms & Requirement AI

### 2.1 Norm Configuration
Admin defines the rules that govern the entire institution. These 5 fields are critical for the AI calculation:
*   `faculty_student_ratio`: Integer (e.g. `15` for 1:15).
*   `max_age`: Integer (e.g. `38`).
*   `workload_hours_per_week`: Integer (e.g. `18`).
*   `min_qualification`: String (e.g. `"M.E./M.Tech"`).
*   `grade_requirement`: String (e.g. `"First Class"`).

### 2.2 Requirement Validation (AI-Assisted)
**Endpoint**: `POST /api/requirements/validate`
**UI Action**: Call this on the "Review Requirement" screen to generate the **"Suggested Requirement Summary"**.
*   **Actual LLM Output**:
    ```json
    {
      "ai_summary": "Based on current intake, requirement appears NORMAL...",
      "confidence_score": 0.95,
      "insights": ["Faculty requirement changed by 5% vs last year"],
      "anomalies": [...] 
    }
    ```

---

## 3. Step 2: Vacancy Intelligence (Multi-Norm Engine)

The system identifies vacancies not just by numbers, but by **Norm Compliance**.

### 3.1 Unified AI Analysis Endpoint
**Endpoint**: `POST /api/vacancies/ai-analysis`
**UI Action**: Use this to show the **"AI-recommended vacancy list with justification"**.

*   **Actual LLM Output**:
    ```json
    {
      "system_vacancy": 5,
      "ai_analysis": {
        "ai_suggested_vacancy": 6,
        "norm_compliance_score": 0.75,
        "justification": "System found 2 faculty members over 38 years old and 1 with only a B.E. (M.Tech required).",
        "overloaded": ["Thermal Engineering Lab"],
        "underutilized": ["Part-time staff"],
        "insights": ["High growth in student intake requires 1 additional CHB"]
      }
    }
    ```

### 3.2 UI Display Rules:
1.  **Requirement Summary**: Display the `ai_summary` in a prominent header on the Requirement Approval page.
2.  **Vacancy Recommendation**: Show `ai_suggested_vacancy` next to the system count.
3.  **Justification Card**: Always show the `justification` string to provide transparency for "faster and more accurate approvals."
4.  **Workload Insights**: List the `overloaded` and `underutilized` areas to help the Principal allocate duties.

---

## 4. Anomaly Feedback Loop

Highlight rows in the faculty list where anomalies are present:

| Flag | Logic Trigger | UI Tooltip |
|---|---|---|
| `UNDER_QUALIFIED` | Faculty degree < `min_qualification` | "Does not meet M.Tech requirement." |
| `OVER_AGE` | Current Age > `max_age` | "Exceeds the 38-year DTE limit." |

---

## 5. Developer Notes
*   **Loading Indicators**: Show an "AI Analyzing..." spinner during the 2-4 second latency.
*   **Fallbacks**: If AI fails, show the `system_calculation` and a fallback note.
*   **PDF Export**: Use the "Markdown PDF" extension in VS Code to share this guide as a PDF.

---

## 6. Step 3: AI Advertisement Generation (SRS 7.6.3.3)

### 6.1 Business Objectives
AI-powered content generation:
*   Auto-generates advertisements using approved DTE templates.
*   Dynamically fills institute, course, qualification, and reservation details.
*   Supports Marathi and English language output.
*   **Outcome**: Ensures error-free, standardized advertisements with minimal manual effort.

### 6.2 Advertisement Generation API
**Endpoint**: `POST /api/advertisements/generate-ai`
**UI Action**: Trigger this when the Principal clicks "Generate Advertisement" after confirming vacancies.

*   **Payload Example**:
    ```json
    {
      "institution_id": 1,
      "course_id": 10,
      "vacancy_count": 5,
      "deadline": "2026-06-15",
      "application_mode": "Walk-in"
    }
    ```

*   **Actual LLM Output**:
    ```json
    {
      "status": "success",
      "data": {
        "template_ad": {
           "title_en": "CHB Lecturer Recruitment",
           "qualification": "M.E./M.Tech"
        },
        "ai_generated_ad": {
          "english": "Applications are invited for the post of CHB Lecturer...",
          "marathi": "सीएचबी अधिव्याख्याता पदासाठी अर्ज मागवण्यात येत आहेत...",
          "sections_present": {
            "eligibility": true,
            "reservation": true,
            "deadline": true
          },
          "issues": [],
          "confidence_score": 1.0
        }
      }
    }
    ```

### 6.3 UI Display Rules:
1.  **Dual Editor View**: Present the `english` and `marathi` AI-generated strings in side-by-side rich text editors so the Principal can make final minor adjustments.
2.  **Quality Assurance Banner**: If the AI returns any `issues` (e.g., `["MISSING_RESERVATION"]`), show a yellow warning banner prompting the user to manually verify the text.
3.  **Confidence Indicator**: Display the `confidence_score` visually. A score below 0.8 should indicate that the AI might have missed formatting requirements.
