from typing import Any, Dict, List

from app.modules.selection.ai_engine import SelectionAIEngine


class SelectionAIService:
    def __init__(self, engine: SelectionAIEngine):
        self.engine = engine

    async def generate_ai_rankings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate candidate rankings using LLM.
        """
        return await self.engine.generate_ai_rankings(payload)

    async def analyze_selection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates the AI analysis of candidate rankings.
        """
        return await self.engine.analyze(payload)

    async def evaluate_ranking_quality(
        self, 
        ranked_rows: List[Dict[str, Any]], 
        candidate_inputs: List[Dict[str, Any]],
        scoring_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Detailed evaluation of the ranking quality produced by the system.
        """
        payload = {
            "candidates": candidate_inputs,
            "ranking": [r["application_id"] for r in ranked_rows],
            "weights": scoring_weights,
            "results": ranked_rows
        }
        # Masking PII before sending to engine
        masked_candidates = []
        id_map = {}
        for i, c in enumerate(candidate_inputs):
            mask_id = f"CAND-{i+1:03d}"
            id_map[mask_id] = str(c["application_id"])
            
            c_copy = c.copy()
            c_copy["id"] = mask_id
            c_copy.pop("application_id", None)
            c_copy.pop("candidate_id", None)
            c_copy.pop("full_name", None)
            masked_candidates.append(c_copy)

        masked_payload = {
            "candidates": masked_candidates,
            "ranking": [f"CAND-{i+1:03d}" for i, _ in enumerate(candidate_inputs)],
            "weights": scoring_weights
        }
        
        result = await self.engine.analyze(masked_payload)
        
        # Unmask
        unmasked_sugs = []
        for sug in result.get("ranking_suggestions", []):
            mid = sug.get("application_id")
            if mid in id_map:
                sug["application_id"] = id_map[mid]
                unmasked_sugs.append(sug)
        result["ranking_suggestions"] = unmasked_sugs
        
        return result
