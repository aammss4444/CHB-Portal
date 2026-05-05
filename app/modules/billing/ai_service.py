class BillingAIService:
    def __init__(self, engine):
        self.engine = engine

    async def analyze(self, payload: dict) -> dict:
        # PII Masking: Remove sensitive identifiers if needed
        # Assuming the payload is already sanitized by the controller
        return await self.engine.analyze(payload)

    async def validate_generated_bill(self, bill_data: dict) -> dict:
        """
        Specialized wrapper for validating a bill immediately after generation.
        Constructs the appropriate payload for the AI engine.
        """
        # Mapping bill response to AI payload format
        payload = {
            "bill_data": {
                "id": str(bill_data.get("id")),
                "academic_year": bill_data.get("academic_year"),
                "total_amount": float(bill_data.get("gross_amount", 0)),
                "status": bill_data.get("bill_status"),
                "period_start": str(bill_data.get("period_start")),
                "period_end": str(bill_data.get("period_end")),
            },
            "attendance": [
                {
                    "lecture_date": str(item.get("lecture_date")),
                    "lecture_type": item.get("lecture_type"),
                    "hours": 1, # Default to 1 hour per log in this context
                    "rate_applied": float(item.get("rate_per_lecture", 0)),
                    "amount": float(item.get("amount", 0))
                }
                for item in bill_data.get("line_items", [])
            ],
            "norms": {
                "max_lectures_per_day": 6,
                "max_hours_per_month": 60,
                "rate_rules": {} # Could be populated if needed
            }
        }
        return await self.analyze(payload)
