import json
import logging
from app.services.openai_client import call_llm_billing

logger = logging.getLogger(__name__)

class BillingAIEngine:
    async def analyze(self, payload: dict) -> dict:
        prompt = f"""
You are validating a faculty bill in a government system.

Bill Data:
{json.dumps(payload.get('bill_data', {}), indent=2)}

Attendance Logs:
{json.dumps(payload.get('attendance', []), indent=2)}

Norms:
{json.dumps(payload.get('norms', {}), indent=2)}

Tasks:
1. Validate lecture count vs attendance
2. Check workload limits
3. Detect anomalies (overbilling, missing logs)
4. Predict approval readiness
5. Flag treasury objections

Return STRICT JSON:
{{
  "validation_status": "VALID | REVIEW_REQUIRED | INVALID",
  "issues": [
    {{
      "type": "OVERBILLING | MISSING_LOG | POLICY_VIOLATION",
      "severity": "LOW | MEDIUM | HIGH",
      "description": ""
    }}
  ],
  "approval_probability": 0.0,
  "risk_level": "LOW | MEDIUM | HIGH",
  "treasury_flags": [],
  "insights": [],
  "confidence_score": 0.0
}}
"""
        raw = await call_llm_billing(prompt)

        if not raw:
            return self._fallback()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI billing response: {e}")
            return self._fallback()

        return self._validate(parsed)

    def _fallback(self) -> dict:
        return {
            "validation_status": "REVIEW_REQUIRED",
            "issues": [{
                "type": "AI_FAILURE",
                "severity": "LOW",
                "description": "Fallback triggered due to AI or parsing failure"
            }],
            "approval_probability": 0.5,
            "risk_level": "LOW",
            "treasury_flags": [],
            "insights": ["System fallback used"],
            "confidence_score": 0.5
        }

    def _validate(self, data: dict) -> dict:
        return {
            "validation_status": data.get("validation_status", "REVIEW_REQUIRED"),
            "issues": data.get("issues", []),
            "approval_probability": float(data.get("approval_probability", 0.5)),
            "risk_level": data.get("risk_level", "LOW"),
            "treasury_flags": data.get("treasury_flags", []),
            "insights": data.get("insights", []),
            "confidence_score": float(data.get("confidence_score", 0.5))
        }
