from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.services.llm_service import llm_service


class AuditAIEngine:
    async def generate_report(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        violations: List[Dict[str, Any]] = []
        insights: List[str] = []

        if not logs:
            return {
                "audit_summary": "No audit records found for selected period.",
                "violations": [],
                "risk_level": "LOW",
                "insights": ["No detectable policy deviation in selected window."],
            }

        actions = Counter(str(row.get("action", "")).upper() for row in logs)
        role_counts = Counter(str(row.get("role", "UNKNOWN")).upper() for row in logs)
        by_entity = Counter(str(row.get("entity_name", "")).upper() for row in logs)

        review_age_violations = 0
        by_entity_id: dict[tuple[str, str], list[Dict[str, Any]]] = defaultdict(list)
        for row in logs:
            by_entity_id[(str(row.get("entity_name")), str(row.get("entity_id")))].append(row)

        for key, entries in by_entity_id.items():
            sorted_entries = sorted(entries, key=lambda e: e.get("timestamp") or now)
            first_ts = sorted_entries[0].get("timestamp")
            last_ts = sorted_entries[-1].get("timestamp")
            if first_ts and last_ts and (last_ts - first_ts) > timedelta(days=14):
                review_age_violations += 1

        if review_age_violations:
            violations.append(
                {
                    "type": "DELAYED_APPROVAL_FLOW",
                    "severity": "MEDIUM",
                    "message": f"{review_age_violations} entities show prolonged processing timelines (>14 days).",
                }
            )

        if actions.get("PUBLISHED", 0) > actions.get("APPROVED", 0):
            violations.append(
                {
                    "type": "POTENTIAL_SKIPPED_APPROVAL",
                    "severity": "HIGH",
                    "message": "Published events exceed approved events; check workflow integrity.",
                }
            )

        if role_counts.get("TREASURY", 0) > 0 and role_counts.get("DIRECTORATE", 0) == 0:
            violations.append(
                {
                    "type": "UNUSUAL_ACCESS_PATTERN",
                    "severity": "LOW",
                    "message": "Treasury actions observed without corresponding Directorate activity in selected period.",
                }
            )

        insights.append(f"Most active entities: {', '.join([k for k, _ in by_entity.most_common(3)])}.")
        insights.append(f"Action frequency snapshot: {dict(actions.most_common(6))}.")

        bottlenecks = [k for k, v in by_entity.items() if v >= 10]
        if bottlenecks:
            insights.append(f"Potential bottleneck entities (high touch volume): {', '.join(bottlenecks[:5])}.")

        llm_insights = await self._llm_audit_insights(logs, violations)
        if llm_insights:
            insights.extend(llm_insights)

        risk_level = "LOW"
        if any(v["severity"] == "HIGH" for v in violations):
            risk_level = "HIGH"
        elif any(v["severity"] == "MEDIUM" for v in violations):
            risk_level = "MEDIUM"

        return {
            "audit_summary": (
                f"Analyzed {len(logs)} audit logs across {len(by_entity)} entities. "
                f"Detected {len(violations)} potential compliance deviations."
            ),
            "violations": violations,
            "risk_level": risk_level,
            "insights": insights,
            "approval_timeline": {"total_events": len(logs), "entity_count": len(by_entity)},
            "bottlenecks": bottlenecks[:10],
        }

    async def _llm_audit_insights(self, logs: List[Dict[str, Any]], violations: List[Dict[str, Any]]) -> List[str]:
        prompt = (
            "You are a compliance audit assistant. Return JSON {'insights': [..]} with up to 3 concise observations "
            "using only provided data.\n"
            f"Recent logs sample: {logs[:20]}\nViolations: {violations}"
        )
        result = await llm_service.analyze_custom_json(prompt)
        if not result:
            return []
        data = result.get("insights", [])
        if not isinstance(data, list):
            return []
        return [str(item).strip() for item in data if str(item).strip()][:3]
