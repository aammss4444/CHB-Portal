import logging
from typing import Optional, Dict, Any
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class RequirementAIEngine:
    async def analyze_requirement(self, data: Dict[str, Any], history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyzes generated faculty requirements and returns an AI-driven analysis.
        
        Input:
            data: {
                "intake_id": int,
                "approved_seats": int,
                "actual_admitted": int,
                "computed_required_count": int,
                "norm_ratio": float,
                "branch_level": str
            }
            history: {
                "previous_required_count": int,
                "previous_actual_admitted": int
            } (optional)
        """
        anomalies = []
        insights = []
        confidence_score = 1.0

        actual = data.get("actual_admitted", 0)
        approved = data.get("approved_seats", 0)
        required = data.get("computed_required_count", 0)

        # 1. Admission Overflow
        if actual > approved:
            overflow_count = actual - approved
            overflow_percent = (overflow_count / approved * 100) if approved > 0 else 100
            anomalies.append({
                "type": "ADMISSION_OVERFLOW",
                "severity": "HIGH",
                "message": f"Actual admitted students ({actual}) exceeds approved seats ({approved}).",
                "insight": f"Overflow detected: {overflow_count} students ({overflow_percent:.1f}%).",
                "recommendation": "Verify intake approval limits and consider increasing faculty allocation."
            })
            insights.append(f"Admission overflow of {overflow_percent:.1f}% detected.")

        # 2. Zero / Invalid Faculty
        if required <= 0:
            anomalies.append({
                "type": "INVALID_FACULTY_COUNT",
                "severity": "CRITICAL",
                "message": f"Computed faculty requirement is {required}.",
                "insight": "System logic or intake data resulting in zero/negative faculty needs.",
                "recommendation": "Review intake definitions and norm ratios for this level."
            })
            insights.append("Critical: Faculty requirement is zero or negative.")
            confidence_score = 0.5

        # 3. Growth Detection (if history exists)
        if history and history.get("previous_required_count") is not None:
            prev_required = history["previous_required_count"]
            if prev_required > 0:
                growth = ((required - prev_required) / prev_required) * 100
                insights.append(f"Faculty requirement changed by {growth:.1f}% compared to last year.")
                
                if growth > 30:
                    severity = "MEDIUM"
                    confidence_score -= 0.2
                    anomalies.append({
                        "type": "UNUSUAL_GROWTH",
                        "severity": severity,
                        "message": f"Faculty requirement increased by {growth:.1f}% year-over-year.",
                        "insight": f"Significant requirement jump from {prev_required} to {required}.",
                        "recommendation": "Verify if the intake increase is officially approved for the current academic year."
                    })
            
            prev_admitted = history.get("previous_actual_admitted", 0)
            if prev_admitted > 0:
                admitted_growth = ((actual - prev_admitted) / prev_admitted) * 100
                insights.append(f"Student intake increased by {admitted_growth:.1f}% compared to last year.")

        # Final Insights
        insights.append(f"Current faculty requirement set to {required} based on {data.get('branch_level', 'Unknown')} norms.")
        
        # 4. LLM Live Analysis Augmentation
        if llm_service.enabled:
            llm_result = await llm_service.analyze_requirement(data, history)
            if llm_result:
                # Merge LLM anomalies (avoid duplicates by checking type)
                existing_types = {a["type"] for a in anomalies}
                for la in llm_result.get("anomalies", []):
                    if la.get("type") not in existing_types:
                        anomalies.append(la)
                
                # Merge LLM insights
                for li in llm_result.get("insights", []):
                    if li not in insights:
                        insights.append(li)
                
                # Combine confidence (conservative approach: use average)
                llm_confidence = llm_result.get("confidence_score")
                try:
                    llm_confidence_value = float(llm_confidence)
                except (TypeError, ValueError):
                    llm_confidence_value = 0.5
                llm_confidence_value = max(0.0, min(1.0, llm_confidence_value))
                confidence_score = (confidence_score + llm_confidence_value) / 2

        # Clamp confidence score
        confidence_score = max(0.0, min(1.0, round(confidence_score, 2)))

        ai_summary = "Based on current intake and norms, required faculty is {}. ".format(required)
        
        if history and history.get("previous_required_count"):
            ai_summary += "Compared to last year, intake changed by {:.1f}%. ".format(admitted_growth if 'admitted_growth' in locals() else 0)
            
        if anomalies:
            ai_summary += "The requirement appears INCONSISTENT. Please review the highlighted anomalies."
        else:
            ai_summary += "The requirement appears NORMAL."

        result = {
            "ai_summary": ai_summary,
            "anomalies": anomalies,
            "confidence_score": float(confidence_score),
            "insights": insights,
            "status": "ANOMALY_DETECTED" if anomalies else "OK",
            "ai_engine_version": llm_service.engine_version()
        }
        
        if anomalies:
            logger.warning(f"AI Anomaly Detected in Requirement: {anomalies}")
            
        return result

