from app.modules.attendance.ai_engine import AttendanceAIEngine

class AttendanceAIService:
    def __init__(self, engine: AttendanceAIEngine):
        self.engine = engine

    async def analyze(self, payload: dict) -> dict:
        return await self.engine.analyze(payload)

    async def evaluate_anomalies(self, anomalies: list) -> dict:
        # Backward compatibility for list_anomalies
        if not anomalies:
            return {"anomalies": [], "risk_level": "LOW", "insights": ["No anomalies found"], "confidence_score": 0.95}
        # We can extract a payload for the new engine
        payload = {"logs": [a for a in anomalies]} # dummy conversion
        return await self.engine.analyze(payload)
