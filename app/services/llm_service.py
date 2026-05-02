import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.enabled = settings.ENABLE_LLM
        self.provider = (settings.LLM_PROVIDER or "").lower()
        self.model_name = "N/A"
        self.base_url = settings.OLLAMA_BASE_URL
        self.timeout = max(5, settings.LLM_TIMEOUT_SECONDS)
        self.model = None
        
        if not self.enabled:
            return

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "ollama":
            self.model_name = settings.OLLAMA_MODEL
            logger.info("Ollama provider initialized with model: %s", self.model_name)
        elif self.provider == "openai":
            self.model_name = settings.OPENAI_MODEL
            if not settings.OPENAI_API_KEY:
                logger.error("OpenAI API Key missing. Disabling LLM.")
                self.enabled = False
            else:
                logger.info("OpenAI provider initialized with model: %s", self.model_name)
        else:
            logger.error("Unsupported LLM provider '%s'. Disabling LLM.", self.provider)
            self.enabled = False

    async def analyze_requirement(self, data: Dict[str, Any], history: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Orchestrates LLM analysis based on configured provider.
        """
        if not self.enabled:
            return None

        prompt = self._build_prompt(data, history)

        raw = None
        if self.provider == "gemini":
            raw = await self._analyze_gemini(prompt)
        elif self.provider == "ollama":
            raw = await self._analyze_ollama(prompt)
        elif self.provider == "openai":
            raw = await self._analyze_openai(prompt)
        
        return self._normalize_requirement_response(raw)

    async def analyze_custom_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Generic JSON-analysis helper for module-specific AI engines.
        Expects provider to return JSON object.
        """
        if not self.enabled:
            return None

        raw = None
        if self.provider == "gemini":
            raw = await self._analyze_gemini(prompt)
        elif self.provider == "ollama":
            raw = await self._analyze_ollama(prompt)
        elif self.provider == "openai":
            raw = await self._analyze_openai(prompt)
        return raw if isinstance(raw, dict) else None

    def engine_version(self) -> str:
        if not self.enabled:
            return "1.0-Rule-Based"
        if self.provider == "ollama":
            return f"2.0-Ollama-{self.model_name}"
        if self.provider == "gemini":
            return f"2.0-Gemini-{self.model_name}"
        if self.provider == "openai":
            return f"2.0-OpenAI-{self.model_name}"
        return "2.0-LLM"

    def _init_gemini(self) -> None:
        if not settings.GEMINI_API_KEY:
            logger.warning("Gemini API Key missing, disabling LLM.")
            self.enabled = False
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            self.model_name = "gemini-1.5-flash"
        except Exception as exc:
            logger.error("Gemini init failed, disabling LLM: %s", exc)
            self.enabled = False

    def _build_prompt(self, data: Dict[str, Any], history: Optional[Dict[str, Any]] = None) -> str:
        return f"""
        You are an AI auditor for a Technical Education Department (CHB Portal).
        Analyze the following faculty requirement data and provide a professional audit.

        Current Data:
        {json.dumps(data, indent=2)}

        Historical Data (Last Year):
        {json.dumps(history, indent=2) if history else "No history available"}

        System Norms:
        - Ratio: {data.get('norm_ratio', 'Unknown')}
        - Level: {data.get('branch_level', 'Unknown')}

        Output MUST be in valid JSON format with the following keys:
        - anomalies: List of objects with (type, severity, message, insight, recommendation)
        - insights: List of strings summarizing trends or observations
        - confidence_score: Float between 0 and 1

        Be critical about:
        1. Admission overflows (Actual > Approved).
        2. Large growth (>30%) if history is present.
        3. Mathematical consistency.
        
        Strictly return ONLY JSON.
        """

    async def _analyze_gemini(self, prompt: str) -> Optional[Dict[str, Any]]:
        try:
            if self.model is None:
                logger.error("Gemini model is not initialized.")
                return None
            response = self.model.generate_content(prompt)
            return self._parse_json(response.text)
        except Exception as e:
            logger.error("Gemini analysis failed: %s", e)
            return None

    async def _analyze_ollama(self, prompt: str) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    }
                )
                if response.status_code != 200:
                    logger.error("Ollama API error (%s): %s", response.status_code, response.text)
                    return None
                
                result = response.json()
                return self._parse_json(result.get("response", ""))
        except httpx.TimeoutException:
            logger.error("Ollama request timed out after %s seconds.", self.timeout)
            return None
        except Exception as e:
            logger.error("Ollama analysis failed: %s", e, exc_info=True)
            return None
            
    async def _analyze_openai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Asynchronous call to OpenAI Chat Completion API.
        """
        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "You are a professional auditor for a Technical Education Department. Return ONLY valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
                
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error("OpenAI API error (%s): %s", response.status_code, response.text)
                    return None
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return self._parse_json(content)
        except httpx.TimeoutException:
            logger.error("OpenAI request timed out.")
            return None
        except Exception as e:
            logger.error("OpenAI analysis failed: %s", e, exc_info=True)
            return None

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            logger.error("LLM returned non-object JSON payload: %s", type(parsed).__name__)
            return None
        except Exception as e:
            logger.error("JSON parsing failed: %s | Raw: %s", str(e), text[:200])
            return None

    def _normalize_requirement_response(self, raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not raw:
            return None

        anomalies_raw = raw.get("anomalies", [])
        insights_raw = raw.get("insights", [])

        anomalies: List[Dict[str, Any]] = []
        if isinstance(anomalies_raw, list):
            for item in anomalies_raw:
                if not isinstance(item, dict):
                    continue
                anomalies.append(
                    {
                        "type": self._normalize_anomaly_type(item.get("type")),
                        "severity": self._normalize_severity(item.get("severity")),
                        "message": str(item.get("message") or "LLM anomaly reported."),
                        "insight": str(item.get("insight") or ""),
                        "recommendation": str(item.get("recommendation") or ""),
                    }
                )

        insights: List[str] = []
        if isinstance(insights_raw, list):
            insights = [str(i).strip() for i in insights_raw if str(i).strip()]

        normalized: Dict[str, Any] = {
            "anomalies": anomalies,
            "insights": insights,
            "confidence_score": self._coerce_confidence(raw.get("confidence_score")),
        }
        return normalized

    def _coerce_confidence(self, value: Any) -> float:
        try:
            if value is None:
                return 0.5
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))

    def _normalize_anomaly_type(self, value: Any) -> str:
        raw = str(value or "").strip().upper().replace(" ", "_")
        if not raw:
            return "UNKNOWN"

        alias_map = {
            "ADMISSION_OVERLOAD": "ADMISSION_OVERFLOW",
            "OVERFLOW": "ADMISSION_OVERFLOW",
            "LARGE_GROWTH": "UNUSUAL_GROWTH",
            "HIGH_GROWTH": "UNUSUAL_GROWTH",
            "INVALID_COUNT": "INVALID_FACULTY_COUNT",
        }
        normalized = alias_map.get(raw, raw)
        allowed = {"ADMISSION_OVERFLOW", "UNUSUAL_GROWTH", "INVALID_FACULTY_COUNT"}
        return normalized if normalized in allowed else "OTHER"

    def _normalize_severity(self, value: Any) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            return raw
        return "MEDIUM"

llm_service = LLMService()
