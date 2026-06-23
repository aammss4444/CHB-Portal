import logging
import json
from typing import List, Optional, Dict, Any
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an AI assistant for a Government Education System (DTE CHB Portal).
Your role is to analyze faculty workload and vacancy requirements.

STRICT RULES:
* Do NOT override system calculations.
* Only provide suggestions and justification.
* Be concise and structured.
* Follow Indian academic norms.
* Output STRICT JSON only.
"""

class VacancyAIEngine:
    async def analyze_vacancy(self, data: Dict[str, Any], faculty_list: List[Dict[str, Any]], history: Optional[Dict[str, Any]] = None, norm_info: Dict[str, Any] = None, intake_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Performs an AI-driven vacancy analysis using all available constraints.
        """
        # 1. Deterministic Baseline Analysis
        rule_based = self._get_rule_based_analysis(data, faculty_list)
        
        if not llm_service.enabled:
            return rule_based

        # 2. LLM Analysis for Vacancy Intelligence
        prompt = self._build_vacancy_prompt(data, faculty_list, history, norm_info, intake_info)
        
        try:
            ai_raw = await llm_service.analyze_custom_json(f"{SYSTEM_PROMPT}\n\nUser Prompt:\n{prompt}")
            
            if not ai_raw:
                return rule_based

            # 3. Merge Rule-based with AI
            return {
                "status": rule_based["status"],
                "ai_suggested_vacancy": ai_raw.get("ai_suggested_vacancy", rule_based["ai_suggested_vacancy"]),
                "overloaded": ai_raw.get("overloaded", []),
                "underutilized": ai_raw.get("underutilized", []),
                "justification": ai_raw.get("justification", rule_based["justification"]),
                "insights": list(set(rule_based["insights"] + ai_raw.get("insights", []))),
                "anomalies": rule_based["anomalies"],
                "confidence_score": ai_raw.get("confidence_score", 0.9),
                "norm_compliance_score": ai_raw.get("norm_compliance_score", 0.0)
            }

        except Exception as e:
            logger.error(f"OpenAI Vacancy Analysis failed: {e}", exc_info=True)
            return rule_based

    def _get_rule_based_analysis(self, data: Dict[str, Any], faculty_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        required = data.get("required_faculty", 0)
        existing_count = data.get("existing_faculty_count", 0)
        suggested = data.get("suggested_vacancy", 0)
        
        anomalies = []
        insights = []
        
        if suggested < 0:
            anomalies.append({
                "type": "OVERSTAFFED",
                "severity": "MEDIUM",
                "message": "Current faculty count exceeds requirements."
            })
        
        if existing_count == 0:
            anomalies.append({
                "type": "NO_FACULTY",
                "severity": "HIGH",
                "message": "Zero faculty records found for this course."
            })

        return {
            "status": "ANOMALY_DETECTED" if anomalies else "OK",
            "ai_suggested_vacancy": int(max(0, suggested)),
            "justification": f"Baseline calculation suggests {suggested} vacancies.",
            "anomalies": anomalies,
            "insights": insights,
            "overloaded": [],
            "underutilized": []
        }

    def _build_vacancy_prompt(self, data: Dict[str, Any], faculty_list: List[Dict[str, Any]], history: Optional[Dict[str, Any]], norm_info: Dict[str, Any], intake_info: Dict[str, Any]) -> str:
        faculty_summary = [
            {
                "designation": f.get("designation"),
                "qualification": f.get("qualification"),
                "qualifications_list": f.get("qualifications_list", []),
                "specialization": f.get("specialization"),
                "employment": f.get("employment_type"),
                "age_approx": f.get("age_approx", "Unknown")
            } for f in faculty_list
        ]

        return f"""
Analyze faculty vacancy for {data.get('course_name', 'Unknown')} at {data.get('institution_name', 'this institution')}.

### 1. INPUT DATA
- **Intake**: {intake_info.get('approved_seats', 0)} (Approved) / {intake_info.get('actual_admitted', 0)} (Actual Admitted)
- **Existing Faculty**: {data.get('existing_faculty_count')} (Total Effective)
- **System Calculation**: {data.get('suggested_vacancy')} vacancies suggested based on ratio.

### 2. DTE NORM CONSTRAINTS
- **Student-Faculty Ratio**: 1:{norm_info.get('faculty_student_ratio', 15)}
- **Workload Norm**: {norm_info.get('workload_hours_per_week', 18)} hours/week
- **Min Qualification**: {norm_info.get('min_qualification', 'Not specified')}
- **Grade Requirement**: {norm_info.get('grade_requirement', 'First Class')}
- **Max Age**: {norm_info.get('max_age', 38)} years

### 3. EXISTING FACULTY PROFILES
{json.dumps(faculty_summary, indent=2)}

### 4. HISTORICAL CONTEXT
{json.dumps(history) if history else "No history available"}

### TASKS
1. Calculate the 'Qualified Vacancy': Subtract faculty who are over-age or under-qualified from the effective count.
2. Evaluate Workload: Based on Intake and Workload Norm, determine if the suggested vacancy is sufficient.
3. Suggest the final CHB Vacancy count.
4. Provide a detailed justification for the Director of Technical Education.

Return JSON ONLY:
{{
  "ai_suggested_vacancy": int,
  "overloaded": ["area 1", ...],
  "underutilized": ["area 1", ...],
  "justification": "text",
  "insights": ["insight 1", ...],
  "norm_compliance_score": 0.0-1.0,
  "confidence_score": 0.0-1.0
}}
"""
