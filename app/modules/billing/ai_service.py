class BillingAIService:
    def __init__(self, engine):
        self.engine = engine

    async def analyze(self, payload: dict) -> dict:
        # PII Masking: Remove sensitive identifiers if needed
        # Assuming the payload is already sanitized by the controller
        return await self.engine.analyze(payload)
