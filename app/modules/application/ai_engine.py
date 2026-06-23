import json
import re
import logging
from typing import Any

from app.services.ocr_service import extract_text
from app.services.openai_client import analyze_documents, openai_ready

logger = logging.getLogger(__name__)


def _mask_sensitive(text: str) -> str:
    if not text:
        return text
    # Mask Aadhaar-like numbers
    return re.sub(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}\b", "XXXX-XXXX-XXXX", text)


class DocumentAIEngine:
    @staticmethod
    def _normalized_result(result: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "document_analysis": result.get("document_analysis", []),
            "missing_documents": result.get("missing_documents", []),
            "mismatches": result.get("mismatches", []),
            "scrutiny_summary": result.get("scrutiny_summary", ""),
            "status": result.get("status", "REQUIRES_REVIEW"),
            "confidence_score": result.get("confidence_score", 0.5),
        }
        if normalized["status"] not in {"COMPLETE", "INCOMPLETE", "REQUIRES_REVIEW"}:
            normalized["status"] = "REQUIRES_REVIEW"
        try:
            normalized["confidence_score"] = float(normalized["confidence_score"])
        except Exception:
            normalized["confidence_score"] = 0.5
        normalized["confidence_score"] = max(0.0, min(1.0, normalized["confidence_score"]))
        return normalized

    async def analyze(self, documents, profile: dict[str, Any]) -> dict[str, Any]:
        logger.info(f"AI Scrutiny: Analyzing {len(documents)} documents for candidate {profile.get('name')}")
        extracted_docs: list[dict[str, Any]] = []
        images_payload = []
        for doc in documents:
            file_path = getattr(doc, "file_path", None) or doc.get("file_path") or doc.get("path")
            doc_type = getattr(doc, "document_type", None) or doc.get("document_type") or doc.get("type")
            
            from pathlib import Path
            backend_root = Path(__file__).resolve().parent.parent.parent.parent
            abs_file_path = str(backend_root / file_path) if file_path else ""
            
            logger.info(f"AI Scrutiny: Extracting text from {doc_type} ({abs_file_path})...")
            text = await extract_text(abs_file_path)
            text = _mask_sensitive(text)
            
            snippet = text[:50].replace('\n', ' ') + "..." if text else "EMPTY"
            logger.info(f"AI Scrutiny: Extracted {len(text)} chars from {doc_type}. Snippet: {snippet}")
            
            extracted_docs.append({"type": doc_type, "text": text[:3000]})
            
            try:
                import os
                import base64
                
                abs_path_obj = Path(abs_file_path)
                if abs_path_obj.exists() and abs_file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                    with open(abs_file_path, "rb") as f:
                        b64_str = base64.b64encode(f.read()).decode('utf-8')
                    ext = abs_file_path.split('.')[-1].lower()
                    mime = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
                    images_payload.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64_str}",
                            "detail": "low"
                        }
                    })
            except Exception as e:
                logger.warning(f"Failed to read image {abs_file_path} for vision: {str(e)}")

        prompt = f"""
Candidate Profile:
Name: {profile.get('name')}
Qualifications: {profile.get('qualifications')}
Experience: {profile.get('experience')}

Documents:
{json.dumps(extracted_docs, ensure_ascii=False)}

Tasks:
1. Extract key info (degree, year, university)
2. Compare with profile
3. Detect missing required documents
4. Visually compare the candidate's photo with the photo on the Aadhar card to verify they match.
5. Verify every candidate profile detail against the Aadhar card details and other submitted documents.
6. Detect any mismatches in textual details or visual face match.
7. Generate a comprehensive and detailed scrutiny summary based on visual and textual verification.
8. Classify application

Return JSON:
{{
  "document_analysis": [
    {{
      "document_type": "...",
      "extracted_fields": {{
        "degree": "...",
        "year": "...",
        "university": "..."
      }},
      "issues": []
    }}
  ],
  "missing_documents": [],
  "mismatches": [],
  "scrutiny_summary": "",
  "status": "COMPLETE | INCOMPLETE | REQUIRES_REVIEW",
  "confidence_score": 0.0
}}
"""
        try:
            if not openai_ready():
                raise RuntimeError("OPENAI_UNAVAILABLE")
            raw = await analyze_documents(prompt, images=images_payload)
            result = self._normalized_result(json.loads(raw))
        except Exception:
            result = self._normalized_result({
                "document_analysis": [],
                "missing_documents": [],
                "mismatches": [],
                "status": "REQUIRES_REVIEW",
                "scrutiny_summary": "AI parsing failed or unavailable; manual scrutiny required.",
                "confidence_score": 0.5,
            })
        return result
