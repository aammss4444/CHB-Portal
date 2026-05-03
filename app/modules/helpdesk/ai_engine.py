from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.services.llm_service import llm_service


class HelpdeskAIEngine:
    def __init__(self) -> None:
        # Approved knowledge snippets only.
        self.knowledge_base: List[Dict[str, str]] = [
            {
                "question": "How do I generate faculty requirement?",
                "answer_en": "Step 1: define intake, generate requirement, then validate anomalies using requirements APIs.",
                "answer_mr": "स्टेप 1: intake निश्चित करा, requirement generate करा आणि anomalies validate करा.",
            },
            {
                "question": "How to process vacancy and advertisement?",
                "answer_en": "Step 2 suggests vacancy from requirement/faculty data; Step 3 needs CONFIRMED vacancy assessment before advertisement generation.",
                "answer_mr": "स्टेप 2 मध्ये vacancy सुचवली जाते; स्टेप 3 साठी advertisement generate करण्यापूर्वी CONFIRMED assessment आवश्यक आहे.",
            },
            {
                "question": "How is billing approved?",
                "answer_en": "Step 8 follows PRINICPAL -> RO -> DIRECTORATE -> TREASURY approval chain after draft bill generation and submission.",
                "answer_mr": "स्टेप 8 मध्ये बिल मंजुरी क्रम: PRINCIPAL -> RO -> DIRECTORATE -> TREASURY.",
            },
            {
                "question": "Who can view audit report?",
                "answer_en": "Audit AI report endpoint is admin-only and provides compliance insights.",
                "answer_mr": "Audit AI report endpoint फक्त admin साठी उपलब्ध आहे.",
            },
        ]

    async def answer_query(self, question: str) -> Dict[str, Any]:
        language = self._detect_language(question)
        match, score = self._best_match(question)

        if not match:
            fallback = (
                "I could not find a trusted answer in approved CHB Portal knowledge. Please contact admin support."
                if language == "EN"
                else "मान्यताप्राप्त CHB Portal माहितीमध्ये उत्तर सापडले नाही. कृपया admin support शी संपर्क साधा."
            )
            return {"answer": fallback, "confidence": 0.35, "language": language}

        answer = match["answer_en"] if language == "EN" else match["answer_mr"]
        answer = await self._llm_refine(answer, question, language)
        return {"answer": answer, "confidence": round(min(0.95, max(0.4, score)), 2), "language": language}

    def _best_match(self, question: str) -> Tuple[Dict[str, str] | None, float]:
        q_tokens = set(self._tokenize(question))
        best = None
        best_score = 0.0
        for item in self.knowledge_base:
            k_tokens = set(self._tokenize(item["question"]))
            if not q_tokens or not k_tokens:
                continue
            overlap = len(q_tokens.intersection(k_tokens))
            score = overlap / max(1, len(k_tokens))
            if score > best_score:
                best = item
                best_score = score
        return best, best_score

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [token for token in re.split(r"[^a-zA-Z0-9\u0900-\u097F]+", text.lower()) if token]

    @staticmethod
    def _detect_language(text: str) -> str:
        return "MR" if re.search(r"[\u0900-\u097F]", text or "") else "EN"

    async def _llm_refine(self, answer: str, question: str, language: str) -> str:
        prompt = (
            "Rewrite the approved answer in concise, user-friendly style without adding new facts. "
            "Return JSON with key 'answer'.\n"
            f"Language: {language}\nQuestion: {question}\nApproved answer: {answer}"
        )
        result = await llm_service.analyze_custom_json(prompt)
        if not result:
            return answer
        refined = result.get("answer")
        return str(refined).strip() if refined else answer
