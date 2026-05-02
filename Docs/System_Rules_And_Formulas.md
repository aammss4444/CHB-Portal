# CHB Portal — System Rules, Formulas & Anomaly Logic

This document defines the core business logic, mathematical formulas, and anomaly detection rules used across all modules of the CHB (Clock Hour Basis) Portal.

---

## 1. Step 1: Faculty Requirement Generation

### 1.1 Calculation Formula
The system calculates the number of required faculty members based on student intake and approved norms.

$$ \text{Required Faculty} = \lceil \frac{\max(\text{Approved Seats}, \text{Actual Admitted})}{\text{Norm Ratio}} \rceil $$

*   **Max Logic**: The system takes the higher value between approved seats and actual admitted students (typical Government budgeting logic).
*   **Norm Ratio**: Defined by Admin per Level (e.g., UG = 20:1, PG = 15:1).

### 1.2 Anomaly Rules (Requirement)
| Anomaly Type | Severity | Rule / Formula |
| :--- | :--- | :--- |
| **Admission Overflow** | HIGH | `Actual Admitted > Approved Seats` |
| **Zero/Negative Calculation** | CRITICAL | `Computed Required Count <= 0` |

### 1.3 AI Validation Engine (Augmentation)
The AI layer provides deeper analysis and confidence scoring based on historical trends and data irregularities.

| Check Type | Severity | Logic / Formula |
| :--- | :--- | :--- |
| **Admission Overflow %** | HIGH | `((Actual - Approved) / Approved) * 100`. Confidence penalty: -0.3 |
| **Unusual Growth** | MEDIUM | `((Current - Previous) / Previous) * 100 > 30%`. Confidence penalty: -0.2 |
| **Invalid Faculty Needs**| CRITICAL | `Required <= 0`. Confidence penalty: -0.5 |

**Confidence Score Calculation**:
*   Starts at **1.0**.
*   Clamped between **0.0** and **1.0**.
*   Reductions applied based on anomaly severity.

---

## 2. Step 2: Vacancy Identification

### 2.1 Calculation Formula
The vacancy count for a course is the gap between required faculty and current effective faculty.

$$ \text{Suggested Vacancy} = \text{Required Count} - \text{Effective Existing Faculty} $$

### 2.2 Anomaly Rules (Vacancy)
| Anomaly Type | Severity | Rule / Formula |
| :--- | :--- | :--- |
| **High Vacancy Ratio** | HIGH | `(Suggested Vacancy / Required Count) * 100 > 50%` |
| **No Faculty Data** | HIGH | `Effective Existing == 0` |
| **Unchanged Vacancy** | LOW | `Suggested Vacancy == Previous Year Confirmed Vacancy` |
| **Deputation Check** | MEDIUM | `Employment Type == "DEPUTED_IN"` (Requires verification of orders) |
| **Qualification Mismatch**| MEDIUM | No common keywords between `Faculty Specialization` and `Course Name` |

### 2.3 AI Vacancy Intelligence Engine (Augmentation)
The AI layer analyzes faculty quality and institutional risk to suggest optimized vacancy counts.

| Check Type | Severity | Logic / Formula |
| :--- | :--- | :--- |
| **Low Qual Majority** | MEDIUM | `(Faculty with < Masters / Total) * 100 > 60%`. Confidence penalty: -0.2 |
| **Spec Mismatch %** | MEDIUM | `(Mismatched Faculty / Total) * 100 > 30%`. Confidence penalty: -0.2 |
| **Instability Risk** | MEDIUM | `(Deputed Faculty / Total) * 100 > 40%`. |

**Smart Vacancy Adjustments**:
*   **Specialization Gap**: `Suggested Vacancy + 1` if mismatch > 30%.
*   **Instability Gap**: `Suggested Vacancy + 1` if deputation > 50%.
*   **Quality Override**: If overstaffed but `PhD Count == 0`, AI prevents reduction of vacancy to protect quality.

**Confidence Score Calculation**:
*   Starts at **1.0**.
*   Reductions: HIGH (-0.3), MEDIUM (-0.2), LOW (-0.1).

---

## 3. Step 3: AI Advertisement Engine (Augmentation)
The AI layer enhances template-generated advertisements for professional tone and compliance.

### 3.1 Compliance & Quality Checks
| Check Type | Severity | Logic / Formula |
| :--- | :--- | :--- |
| **Missing Eligibility** | HIGH | Flag if `qualification` details are vague or missing. |
| **Missing Deadline** | HIGH | Flag if `application_end_date` is not explicitly mentioned. |
| **Bilingual Gap** | MEDIUM | Detect if `Marathi` version significantly differs in word count/meaning from `English`. |
| **Tone Check** | LOW | Identify non-formal or ambiguous phrasing (e.g., "apply soon" instead of specific dates). |

**Smart Enhancements**:
*   **Formalization**: Converts raw placeholders into government-style formal phrasing.
*   **Structure Enforcement**: Ensures Introduction, Vacancy Table, Eligibility, and Process sections are logically separated.

**Confidence Score Calculation**:
*   Starts at **1.0**.
*   Reductions: Missing Section (-0.3), Language Mismatch (-0.2), Weak Content (-0.1).
*   Status becomes `NEEDS_IMPROVEMENT` if score < 0.8.

---

## 3. Step 4: AI Document Validation Engine

The AI validation engine runs on every uploaded document to prevent fraudulent or low-quality submissions.

### 3.1 Validation Status Priority
1.  **FAIL** on any rule $\rightarrow$ `INVALID`
2.  **WARNING** on any rule (with no FAILs) $\rightarrow$ `SUSPICIOUS`
3.  **PASS** on all rules $\rightarrow$ `VALID`

### 3.2 Rules & Thresholds
| Rule Name | Severity | Threshold / Logic |
| :--- | :--- | :--- |
| **File Format Check** | FAIL | Must be parseable PDF or Image (JPG/PNG/TIFF) |
| **File Size Check** | FAIL | `File Size > 2048 KB (2 MB)` |
| **Blank Document Check** | WARNING | `PDF Text Length < 50 characters` |
| **Duplicate Check** | FAIL | `SHA-256 Hash` matches another doc in the same application |
| **Photo Resolution** | FAIL | `Width < 200px` OR `Height < 200px` |
| **JPEG Quality** | FAIL | `Width < 640px` OR `Height < 480px` |
| **TIFF Quality** | FAIL | `DPI < 600 x 600` |
| **Year Detection** | WARNING | No year matching `19xx` or `20xx` found in Degree/Marksheet text |

---

## 4. Step 5: Selection & AI Ranking Engine

### 4.1 Scoring Components (Raw 0-100)
| Component | Formula / Logic |
| :--- | :--- |
| **Qualification** | PhD (100), Masters (83), Bachelors (50), Else (0) |
| **Experience** | `(min(Years, 25) / 25) * 100` (Capped at 25 years) |
| **Interview** | Raw marks entered by panel (0-100) |
| **Publication** | `(min(Count, 10) / 10) * 100` (Capped at 10 publications) |
| **Reservation** | SC/ST (100), OBC/VJNT/EWS (60), Open (0) (Used as tie-breaker weight) |

### 4.2 Final Score Formula
$$ \text{Final Score} = \sum (\text{Component Raw} \times \frac{\text{Component Weight}}{100}) $$

### 4.3 Anomaly Rules (Selection)
| Anomaly Type | Severity | Rule / Formula |
| :--- | :--- | :--- |
| **Uniform Marks** | HIGH | All candidates in a round have identical interview marks |
| **Qual-Rank Gap** | MEDIUM | Candidate with PhD (Qual 100) is ranked below 3rd position |
| **Reservation Gap** | LOW | Reserved candidates applied but 100% of selections are Open category |
| **Single Candidate** | MEDIUM | Only 1 candidate appeared for the interview |

---

## 5. Step 7: Attendance Anomaly Logic

The system monitors daily lecture logs for patterns of fraud or error.

### 5.1 Global Policies
*   **Max Daily Lectures**: Configured via `MAX_DAILY_LECTURES_POLICY` (Default = 6).

### 5.2 Anomaly Rules (Attendance)
| Anomaly Type | Severity | Rule / Formula |
| :--- | :--- | :--- |
| **Holiday Logging** | HIGH | Log date is marked "HOLIDAY" in Academic Calendar |
| **Excessive Lectures** | HIGH | `Daily Logs > Max Policy (6)` |
| **Backdated Log** | MEDIUM | `(Log Creation Date - Lecture Date) > 3 days` |
| **Subject Mismatch** | MEDIUM | `Logged Subject != Timetable Subject` for that slot |
| **Duplicate Topic** | MEDIUM | Same topic string logged $> 3$ times in 30 days |
| **Unusual Attendance**| LOW | `Logged Attendance > 1.1 * Average` for that specific class |
| **Consistent Fullness**| LOW | Max lectures logged for $\ge 15$ consecutive working days |
| **Missing Logs** | MEDIUM | Scheduled slots exist in timetable but 0 logs found for the date |
| **Period Closed** | HIGH | Log submitted after the monthly period was locked/closed |

---

## 6. Step 8: Billing Formulas

### 6.1 Calculation Logic
1.  **Filter**: Only `VERIFIED` logs are included.
2.  **Capping**: Only up to the `Max Daily Policy` (6) lectures per day are billable.
    *   *Tie-break*: If a faculty logs 8 lectures, the system selects the first 6 based on Slot Number.
3.  **Rate Resolution**: Rate is fetched based on `(Faculty Designation, Lecture Type)`.

### 6.2 Formula
$$ \text{Line Item Amount} = \text{Resolved Rate} \times 1 \text{ (per lecture unit)} $$
$$ \text{Gross Bill Amount} = \sum \text{Included Line Item Amounts} $$

---

## 7. Step 9: Payment Idempotency & Gates

### 7.1 Payment Eligibility
A bill is only eligible for payment if:
1.  Status is `TREASURY_PROCESSED`.
2.  `is_locked` is `True`.
3.  No successful `payment_transaction` exists for the same `bill_id`.

---
*Last Updated: 2026-04-24*
*Source: Core Business Engines (`ranking_engine.py`, `anomaly_engine.py`, `document_validator.py`, `bill_calculator.py`)*

---

## 8. April 2026 AI Rules Expansion (Step 5 to Step 10)

This section appends the latest enterprise AI rules added to production code paths while preserving existing deterministic formulas.

### 8.1 Shared AI Output Contract

All new AI modules return:

- structured JSON
- explainable `insights`
- confidence scoring
- advisory-only recommendations (no workflow override)

### 8.2 Step 5: Selection AI Intelligence Rules

Implemented logic includes deterministic checks and LLM-augmented insights.

| Rule Type | Severity | Logic |
| :--- | :--- | :--- |
| Uniform Interview Marks | HIGH | All `interview_total` values equal for a round |
| High Qualification Low Rank | MEDIUM | Qualification raw score >= 100 and rank > 3 |
| Reservation Imbalance | LOW | Reserved-category applicants exist but none selected |

Selection AI output:

```json
{
  "rankings": [],
  "bias_flags": [],
  "insights": [],
  "comparison_dashboard": {
    "top_candidates": [],
    "score_distribution": {},
    "ranking_changes": []
  },
  "confidence_score": 0.0
}
```

### 8.3 Step 7: Attendance Intelligence Rules

AI computes risk from anomaly stream already produced by attendance anomaly engine.

| Rule Type | Severity | Logic |
| :--- | :--- | :--- |
| Repeated Anomaly Pattern | MEDIUM | Same anomaly type appears >= 3 times in filtered dataset |
| Repeated Topic Pattern | LOW | Same subject linked to anomaly >= 4 times |
| Risk Classification | LOW/MEDIUM/HIGH | Based on HIGH/MEDIUM anomaly counts |

Attendance AI output:

```json
{
  "anomalies": [],
  "risk_level": "LOW",
  "insights": [],
  "confidence_score": 0.0
}
```

### 8.4 Step 8: Billing Validation AI Rules

| Rule Type | Severity | Logic |
| :--- | :--- | :--- |
| Max Daily Lecture Policy Risk | HIGH | Per-day line-item count exceeds policy threshold |
| Unverified Log Reference | HIGH | Bill line item missing `lecture_log_id` linkage |
| Attendance High Anomaly Context | MEDIUM | HIGH attendance anomalies exist in billing period |
| Unusually High Bill Rate | MEDIUM | Gross-to-billable ratio is abnormal |

Billing AI output:

```json
{
  "validation_status": "VALID",
  "risk_flags": [],
  "approval_probability": 0.0,
  "insights": []
}
```

### 8.5 Step 9: Audit AI Compliance Rules

| Rule Type | Severity | Logic |
| :--- | :--- | :--- |
| Delayed Approval Flow | MEDIUM | Entity workflow duration > 14 days |
| Potential Skipped Approval | HIGH | Published actions exceed approved actions |
| Unusual Access Pattern | LOW | Treasury actions without expected prior checkpoint patterns |

Audit AI output:

```json
{
  "audit_summary": "...",
  "violations": [],
  "risk_level": "LOW",
  "insights": [],
  "approval_timeline": {},
  "bottlenecks": []
}
```

### 8.6 Step 10: Helpdesk AI Rules

| Rule Type | Behavior |
| :--- | :--- |
| Language Detection | Marathi if Devanagari detected; else English |
| Knowledge Constraint | Only approved FAQ/manual snippets are used |
| Fallback | Returns safe support message if confidence is low |

Helpdesk output:

```json
{
  "answer": "...",
  "confidence": 0.0,
  "language": "EN"
}
```

### 8.7 LLM Safety & Normalization Rules

- Provider-safe runtime with fail-safe fallback.
- Confidence coercion to numeric range [0.0, 1.0].
- Normalized anomaly typing to avoid uncontrolled label drift.
- JSON-only contract via shared `analyze_custom_json(prompt)`.

---
*Rules Expansion Updated: 2026-04-26*
*Scope: Step 5 to Step 10 AI implementation rules*
