import json
import logging
from typing import Any, Dict

from app.services.openai_client import generate_ad, openai_ready

logger = logging.getLogger(__name__)


class AdvertisementAIEngine:
    async def create_ad(self, data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
Generate a CHB Lecturer Advertisement:

Institution: {data['institution_name']}
Course: {data['course_name']}
Level: {data['course_level']}
Vacancies: {data['vacancy_count']}
Qualification: {data['qualification']}
Reservation: {data['reservation']}
Deadline: {data['deadline']}
Application Mode: {data.get('application_mode', 'Walk-in')}

Requirements:
1. Create structured English advertisement
2. Create Marathi equivalent
3. Include:
   * Title
   * Vacancy details
   * Eligibility
   * Reservation
   * Application process
   * Required documents
   * Deadline
   * Venue/Instructions

Return JSON:
{{
  "english": "...",
  "marathi": "...",
  "sections_present": {{
    "eligibility": true,
    "reservation": true,
    "deadline": true
  }},
  "issues": [],
  "confidence_score": 0.0
}}
"""
        try:
            if not openai_ready():
                raise RuntimeError("OPENAI_UNAVAILABLE")
            raw = await generate_ad(prompt)
            parsed = json.loads(raw)
        except Exception as exc:
            logger.error("AI ad generation/parsing failed: %s", exc, exc_info=True)
            issue = "AI_PARSE_FAILED"
            if "OPENAI_UNAVAILABLE" in str(exc):
                issue = "OPENAI_UNAVAILABLE"
            parsed = {
                "english": "",
                "marathi": "",
                "sections_present": {},
                "issues": [issue],
                "confidence_score": 0.5,
            }

        issues = []
        sp = parsed.get("sections_present", {})
        if not sp.get("eligibility"):
            issues.append("MISSING_ELIGIBILITY")
        if not sp.get("reservation"):
            issues.append("MISSING_RESERVATION")
        if not sp.get("deadline"):
            issues.append("MISSING_DEADLINE")

        parsed["issues"] = parsed.get("issues", []) + issues
        score = 1.0 - (0.2 * len(issues))
        parsed["confidence_score"] = max(0.0, min(1.0, score))
        return parsed
