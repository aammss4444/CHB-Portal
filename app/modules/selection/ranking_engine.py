from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel

class CandidateRankingInput(BaseModel):
    application_id: UUID
    candidate_id: UUID
    full_name: str
    category: str
    highest_degree: str
    teaching_experience_years: float
    interview_total: float # 0-100
    publication_count: int

class RankedCandidate(BaseModel):
    application_id: UUID
    candidate_id: UUID
    final_score: Decimal
    rank: int
    result_status: str # SELECTED, WAITLISTED, REJECTED
    waitlist_position: Optional[int] = None
    score_breakdown: Dict[str, Any]
    anomalies: List[Dict[str, str]] = []

def compute_candidate_rankings(
    advertisement_id: UUID,
    candidates: List[CandidateRankingInput],
    vacancy_count: int,
    weights: Any # ScoringWeightConfig-like object or dict
) -> List[RankedCandidate]:
    """
    Pure function to compute candidate rankings based on configurable weights.
    NO DB CALLS.
    """
    
    # 1. Extract weights
    w_qual = Decimal(str(weights.qualification_weight))
    w_exp = Decimal(str(weights.experience_weight))
    w_int = Decimal(str(weights.interview_weight))
    w_pub = Decimal(str(weights.publication_weight))
    w_res = Decimal(str(weights.reservation_weight))

    results = []

    for cand in candidates:
        # -- Qualification Score (Max 100) --
        # PhD: 100, ME: 83, BE: 50, Else: 0
        q_raw = Decimal("0.00")
        if cand.highest_degree in ["PhD", "Doctorate"]:
            q_raw = Decimal("100.00")
        elif cand.highest_degree in ["ME", "MTech", "MCA", "MBA"]:
            q_raw = Decimal("83.00")
        elif cand.highest_degree in ["BE", "BTech", "BSc", "BA", "BCom"]:
            q_raw = Decimal("50.00")
        
        q_weighted = (q_raw * w_qual) / Decimal("100.00")

        # -- Experience Score (Max 100) --
        # 1 year = 4 points (if cap at 25 years = 100)
        # Spec says: min(total_years, 25) / 25 * 100
        e_raw = (Decimal(str(min(cand.teaching_experience_years, 25))) / Decimal("25.00")) * Decimal("100.00")
        e_weighted = (e_raw * w_exp) / Decimal("100.00")

        # -- Interview Score (Already 0-100) --
        i_raw = Decimal(str(cand.interview_total))
        i_weighted = (i_raw * w_int) / Decimal("100.00")

        # -- Publication Score (Max 100) --
        # 1 pub = 10 points (cap at 10)
        p_raw = (Decimal(str(min(cand.publication_count, 10))) / Decimal("10.00")) * Decimal("100.00")
        p_weighted = (p_raw * w_pub) / Decimal("100.00")

        # -- Reservation Tiebreaker (Raw 0-100) --
        # SC/ST: 100, OBC/etc: 60, OPEN: 0
        r_raw = Decimal("0.00")
        if cand.category in ["SC", "ST"]:
            r_raw = Decimal("100.00")
        elif cand.category in ["OBC", "SBC", "VJNT", "EWS"]:
            r_raw = Decimal("60.00")
        
        r_weighted = (r_raw * w_res) / Decimal("100.00")

        final_score = q_weighted + e_weighted + i_weighted + p_weighted + r_weighted

        breakdown = {
            "weights_used": {
                "config_id": str(getattr(weights, "id", "N/A")),
                "config_name": getattr(weights, "config_name", "CUSTOM"),
                "set_by_role": getattr(weights, "set_by_role", "SYSTEM"),
                "qualification_weight": float(w_qual),
                "experience_weight": float(w_exp),
                "interview_weight": float(w_int),
                "publication_weight": float(w_pub),
                "reservation_weight": float(w_res)
            },
            "qualification": {
                "degree": cand.highest_degree,
                "raw_score": float(q_raw),
                "weight": float(w_qual / 100),
                "weighted": float(q_weighted)
            },
            "experience": {
                "years": cand.teaching_experience_years,
                "raw_score": float(e_raw),
                "weight": float(w_exp / 100),
                "weighted": float(e_weighted)
            },
            "interview": {
                "total": cand.interview_total,
                "raw_score": float(i_raw),
                "weight": float(w_int / 100),
                "weighted": float(i_weighted)
            },
            "publication": {
                "count": cand.publication_count,
                "raw_score": float(p_raw),
                "weight": float(w_pub / 100),
                "weighted": float(p_weighted)
            },
            "reservation": {
                "category": cand.category,
                "raw_score": float(r_raw),
                "weight": float(w_res / 100),
                "weighted": float(r_weighted)
            },
            "final_score": float(final_score)
        }

        results.append({
            "application_id": cand.application_id,
            "candidate_id": cand.candidate_id,
            "final_score": final_score,
            "category": cand.category,
            "exp_years": cand.teaching_experience_years,
            "qual_score": q_raw,
            "interview_score": i_raw,
            "score_breakdown": breakdown
        })

    # -- Ranking Logic --
    # Sort by final_score DESC, then tie-break by reservation_raw, then experience_years
    results.sort(key=lambda x: (x["final_score"], x["category"] in ["SC", "ST", "OBC", "SBC", "VJNT", "EWS"], x["exp_years"]), reverse=True)

    ranked_list = []
    for i, res in enumerate(results):
        rank = i + 1
        status = "REJECTED"
        waitlist_pos = None

        if rank <= vacancy_count:
            status = "SELECTED"
        elif rank <= vacancy_count + 3:
            status = "WAITLISTED"
            waitlist_pos = rank - vacancy_count

        ranked_list.append(RankedCandidate(
            application_id=res["application_id"],
            candidate_id=res["candidate_id"],
            final_score=res["final_score"],
            rank=rank,
            result_status=status,
            waitlist_position=waitlist_pos,
            score_breakdown=res["score_breakdown"]
        ))

    # -- Anomaly Detection --
    anomalies = []
    
    # 1. Uniform Marks
    if len(candidates) > 1:
        marks = [c.interview_total for c in candidates]
        if len(set(marks)) == 1:
            anomalies.append({
                "type": "UNIFORM_MARKS",
                "severity": "HIGH",
                "message": "All candidates received identical marks. Review for bias."
            })

    # 2. Qualification Rank Gap
    for r in ranked_list:
        if r.score_breakdown["qualification"]["raw_score"] == 100 and r.rank > 3:
            anomalies.append({
                "type": "QUALIFICATION_RANK_GAP",
                "severity": "MEDIUM",
                "message": f"Highly qualified candidate (PhD) ranked {r.rank}. Verify interview marks."
            })

    # 3. Reservation Underrepresentation
    selected_categories = [r.score_breakdown["reservation"]["category"] for r in ranked_list if r.result_status == "SELECTED"]
    has_reserved = any(c in ["SC", "ST", "OBC", "SBC", "VJNT", "EWS"] for c in selected_categories)
    applied_reserved = any(c.category in ["SC", "ST", "OBC", "SBC", "VJNT", "EWS"] for c in candidates)
    if applied_reserved and not has_reserved:
        anomalies.append({
            "type": "RESERVATION_UNDERREPRESENTATION",
            "severity": "LOW",
            "message": "No reserved category candidate selected. Verify compliance."
        })

    # 4. Single Candidate
    if len(candidates) == 1:
        anomalies.append({
            "type": "SINGLE_CANDIDATE",
            "severity": "MEDIUM",
            "message": "Only one candidate present. Consider re-advertisement."
        })

    # Attach anomalies to the first result for logging (or handle in service)
    for r in ranked_list:
        r.anomalies = anomalies

    return ranked_list
