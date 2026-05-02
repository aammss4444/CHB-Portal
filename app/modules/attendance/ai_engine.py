import json
import logging
from app.services.openai_client import call_llm_attendance

logger = logging.getLogger(__name__)

class AttendanceAIEngine:
    async def analyze(self, payload: dict) -> dict:
        prompt = f"""
You are analyzing faculty attendance logs.

Faculty ID: {payload.get('faculty_id', 'UNKNOWN')}

Attendance Logs:
{json.dumps(payload.get('logs', []), default=str, indent=2)}

Policies:
* Max lectures/day = 6
* Backdated allowed ≤ 3 days

Tasks:
1. Detect anomalies:
   * Duplicate logs
   * Excess lectures
   * Backdated entries
   * Unusual spikes
2. Identify patterns
3. Assign risk level
4. Provide insights

Return STRICT JSON:
{{
  "anomalies": [
    {{
      "type": "DUPLICATE | EXCESS | BACKDATED | SPIKE",
      "severity": "LOW | MEDIUM | HIGH",
      "description": ""
    }}
  ],
  "patterns": [],
  "risk_level": "LOW | MEDIUM | HIGH",
  "insights": [],
  "confidence_score": 0.0
}}
"""
        raw = await call_llm_attendance(prompt)
        
        if not raw:
            return self._fallback()
            
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return self._fallback()
            
        return self._validate(parsed)

    def _fallback(self) -> dict:
        return {
            "anomalies": [{
                "type": "AI_FAILURE",
                "severity": "LOW",
                "description": "Fallback triggered due to AI or parsing failure"
            }],
            "patterns": [],
            "risk_level": "LOW",
            "insights": ["System fallback used"],
            "confidence_score": 0.5
        }

    def _validate(self, data: dict) -> dict:
        return {
            "anomalies": data.get("anomalies", []),
            "patterns": data.get("patterns", []),
            "risk_level": data.get("risk_level", "LOW"),
            "insights": data.get("insights", []),
            "confidence_score": float(data.get("confidence_score", 0.5))
        }
