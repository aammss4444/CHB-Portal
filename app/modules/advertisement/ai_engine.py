import logging
from typing import Any, Dict
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class AdvertisementAIEngine:
    async def create_ad(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses the centralized LLM service to generate a bilingual advertisement.
        """
        if not llm_service.enabled:
            return {
                "english": "",
                "marathi": "",
                "sections_present": {},
                "issues": ["LLM_DISABLED"],
                "confidence_score": 0.0,
            }

        result = await llm_service.generate_advertisement(data)
        
        if not result:
            return {
                "english": "",
                "marathi": "",
                "sections_present": {},
                "issues": ["AI_GENERATION_FAILED"],
                "confidence_score": 0.0,
            }

        # Ensure compliance flags/issues are processed if not in LLM output
        issues = result.get("issues", [])
        sp = result.get("sections_present", {})
        
        if not sp.get("qualifications") and not sp.get("eligibility"):
            issues.append("MISSING_ELIGIBILITY")
        if not sp.get("reservation"):
            issues.append("MISSING_RESERVATION")
        if not sp.get("dates") and not sp.get("deadline"):
            issues.append("MISSING_DEADLINE")

        result["issues"] = list(set(issues))
        return result
