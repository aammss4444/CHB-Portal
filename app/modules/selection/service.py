from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shortlisted_candidate import ShortlistedCandidate
from app.models.interview_marks import InterviewMarks
from app.models.candidate_score import CandidateScore
from app.models.selection_result import SelectionResult, SelectionResultStatus, FinalResultStatus
from app.models.application import Application, ApplicationStatus
from app.models.advertisement import Advertisement, AdvertisementStatus
from app.models.candidate import Candidate
from app.models.candidate_qualification import CandidateQualification
from app.models.candidate_experience import CandidateExperience
from app.models.application_document import ApplicationDocument
from app.models.vacancy_assessment import VacancyAssessment
from app.models.vacancy_anomaly import VacancyAnomaly
from app.models.audit import AuditLog
from app.models.user import User
from app.models.selection_ai_snapshot import SelectionAISnapshot
from app.models.appointment_letter import AppointmentLetter

from app.modules.selection.schemas import (
    ShortlistRequest,
    AttendanceRequest,
    InterviewMarksRequest,
    InterviewMarksUpdateRequest,
    ConfirmSelectionRequest
)
from app.schemas.selection_ai import SelectionAIResponse, SelectionDashboardResponse
from app.modules.selection.ranking_engine import compute_candidate_rankings, CandidateRankingInput
from app.modules.selection.ai_engine import SelectionAIEngine
from app.modules.selection.ai_service import SelectionAIService
from app.modules.scoring_weights.service import ScoringWeightService

class SelectionService:
    def __init__(self):
        self.weight_service = ScoringWeightService()
        self.ai_service = SelectionAIService(SelectionAIEngine())

    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    async def _write_audit(
        self, db: AsyncSession, entity: str, entity_id: Any, action: str, user_id: int, 
        old_value: dict = None, new_value: dict = None
    ):
        eid = str(entity_id)
        db.add(AuditLog(
            entity_name=entity,
            entity_id=eid,
            action=action,
            user_id=user_id,
            old_value=old_value,
            new_value=new_value
        ))

    async def shortlist_candidates(self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: ShortlistRequest):
        ad = (await db.execute(select(Advertisement).where(Advertisement.id == advertisement_id))).scalars().first()
        if not ad:
            self._raise_error(404, "ADVERTISEMENT_NOT_FOUND", "Advertisement not found")
            
        completed = (await db.execute(select(SelectionResult).where(SelectionResult.advertisement_id == advertisement_id))).scalars().first()
        if completed:
             self._raise_error(400, "SELECTION_COMPLETED", "Cannot shortlist for a completed selection process")

        stmt = select(Application).where(Application.id.in_(req.application_ids))
        apps = (await db.execute(stmt)).scalars().all()
        app_map = {app.id: app for app in apps}

        existing_stmt = select(ShortlistedCandidate.application_id).where(ShortlistedCandidate.advertisement_id == advertisement_id)
        existing_ids = set((await db.execute(existing_stmt)).scalars().all())

        for app_id in req.application_ids:
            app = app_map.get(app_id)
            if not app or app.advertisement_id != advertisement_id:
                continue
            if app.status != ApplicationStatus.SUBMITTED.value:
                continue
            if app_id in existing_ids:
                continue

            db.add(ShortlistedCandidate(
                advertisement_id=advertisement_id,
                application_id=app_id,
                candidate_id=app.candidate_id,
                shortlisted_by=current_user.id,
                shortlist_remarks=req.remarks
            ))
            app.status = ApplicationStatus.SHORTLISTED.value

        await self._write_audit(db, "Advertisement", advertisement_id, "SHORTLIST_CANDIDATES", current_user.id)
        await db.commit()

    async def get_shortlisted(self, db: AsyncSession, advertisement_id: UUID) -> List[dict]:
        stmt = (
            select(
                ShortlistedCandidate, 
                Candidate.full_name, 
                Application.application_number,
                InterviewMarks.interview_total
            )
            .join(Application, Application.id == ShortlistedCandidate.application_id)
            .join(Candidate, Candidate.id == ShortlistedCandidate.candidate_id)
            .outerjoin(InterviewMarks, and_(
                InterviewMarks.advertisement_id == advertisement_id, 
                InterviewMarks.application_id == ShortlistedCandidate.application_id
            ))
            .where(ShortlistedCandidate.advertisement_id == advertisement_id)
        )
        rows = (await db.execute(stmt)).all()
        
        results = []
        for sc, name, app_num, int_total in rows:
            qual = (await db.execute(select(CandidateQualification).where(
                and_(CandidateQualification.candidate_id == sc.candidate_id, CandidateQualification.is_highest == True)
            ))).scalars().first()
            
            exp_rows = (await db.execute(select(CandidateExperience).where(
                and_(CandidateExperience.candidate_id == sc.candidate_id, CandidateExperience.experience_type == "TEACHING")
            ))).scalars().all()
            total_exp = 0.0
            for e in exp_rows:
                end = e.to_date or datetime.now().date()
                total_exp += (end - e.from_date).days / 365.25

            results.append({
                "application_id": sc.application_id,
                "candidate_id": sc.candidate_id,
                "candidate_name": name,
                "application_number": app_num,
                "qualification": qual.degree if qual else "N/A",
                "experience_years": round(total_exp, 1),
                "is_present": sc.is_present,
                "interview_total": int_total
            })
        return results

    async def mark_attendance(self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: AttendanceRequest):
        completed = (await db.execute(select(SelectionResult).where(SelectionResult.advertisement_id == advertisement_id))).scalars().first()
        if completed:
             self._raise_error(400, "SELECTION_COMPLETED", "Attendance cannot be updated for completed selection")

        for item in req.attendance:
            await db.execute(
                update(ShortlistedCandidate)
                .where(and_(ShortlistedCandidate.advertisement_id == advertisement_id, ShortlistedCandidate.application_id == item.application_id))
                .values(is_present=item.is_present)
            )
        
        await self._write_audit(db, "Advertisement", advertisement_id, "MARK_ATTENDANCE", current_user.id)
        await db.commit()

    async def enter_marks(self, db: AsyncSession, current_user: User, req: InterviewMarksRequest) -> InterviewMarks:
        ad = (await db.execute(select(Advertisement).where(Advertisement.id == req.advertisement_id))).scalars().first()
        if not ad:
            self._raise_error(404, "ADVERTISEMENT_NOT_FOUND", "Advertisement not found")
            
        # Allow entering marks unless THIS specific candidate is already confirmed
        candidate_confirmed = (await db.execute(
            select(SelectionResult)
            .where(and_(
                SelectionResult.advertisement_id == req.advertisement_id,
                SelectionResult.candidate_id == req.candidate_id,
                SelectionResult.status == FinalResultStatus.CONFIRMED.value
            ))
        )).scalars().first()
        
        if candidate_confirmed:
             self._raise_error(400, "SELECTION_COMPLETED", "Marks cannot be entered for a candidate whose selection is already confirmed")

        sc = (await db.execute(select(ShortlistedCandidate).where(
            and_(ShortlistedCandidate.advertisement_id == req.advertisement_id, ShortlistedCandidate.application_id == req.application_id)
        ))).scalars().first()
        if not sc:
            self._raise_error(400, "CANDIDATE_NOT_SHORTLISTED", "Cannot enter marks for a candidate who is not shortlisted")

        if not sc.is_present:
            sc.is_present = True

        existing = (await db.execute(select(InterviewMarks).where(
            and_(InterviewMarks.advertisement_id == req.advertisement_id, InterviewMarks.application_id == req.application_id)
        ))).scalars().first()
        if existing:
             self._raise_error(409, "MARKS_ALREADY_ENTERED", "Marks already entered. Use PUT to update.")

        total = (req.subject_knowledge + req.teaching_aptitude + req.communication_skills + req.overall_impression) / 4
        
        marks = InterviewMarks(
            advertisement_id=req.advertisement_id,
            application_id=req.application_id,
            candidate_id=req.candidate_id,
            institution_id=req.institution_id,
            subject_knowledge=req.subject_knowledge,
            teaching_aptitude=req.teaching_aptitude,
            communication_skills=req.communication_skills,
            overall_impression=req.overall_impression,
            interview_total=total,
            entered_by=current_user.id
        )
        db.add(marks)
        await db.flush()
        await self._write_audit(db, "InterviewMarks", marks.id, "ENTER_MARKS", current_user.id, new_value=req.model_dump(mode="json"))
        await db.commit()
        await db.refresh(marks)
        return marks

    async def update_marks(self, db: AsyncSession, current_user: User, mark_id: UUID, req: InterviewMarksUpdateRequest) -> InterviewMarks:
        marks = (await db.execute(select(InterviewMarks).where(InterviewMarks.id == mark_id))).scalars().first()
        if not marks:
             self._raise_error(404, "NOT_FOUND", "Marks not found")
        
        from app.dependencies.institution_scope import verify_institution_access
        await verify_institution_access(marks.institution_id, current_user)
        
        if marks.is_locked:
            self._raise_error(403, "MARKS_LOCKED", "Marks are locked after ranking and cannot be edited")

        old_val = {"total": float(marks.interview_total)}
        
        if req.subject_knowledge is not None: marks.subject_knowledge = req.subject_knowledge
        if req.teaching_aptitude is not None: marks.teaching_aptitude = req.teaching_aptitude
        if req.communication_skills is not None: marks.communication_skills = req.communication_skills
        if req.overall_impression is not None: marks.overall_impression = req.overall_impression
        
        marks.interview_total = (marks.subject_knowledge + marks.teaching_aptitude + marks.communication_skills + marks.overall_impression) / 4
        
        await self._write_audit(db, "InterviewMarks", mark_id, "UPDATE_MARKS", current_user.id, old_value=old_val, new_value={"total": float(marks.interview_total)})
        await db.commit()
        await db.refresh(marks)
        return marks

    async def generate_rankings(self, db: AsyncSession, current_user: User, advertisement_id: UUID) -> Dict[str, Any]:
        ad_stmt = select(Advertisement).options(selectinload(Advertisement.assessment)).where(Advertisement.id == advertisement_id)
        ad = (await db.execute(ad_stmt)).scalars().first()
        if not ad:
            self._raise_error(404, "ADVERTISEMENT_NOT_FOUND", "Advertisement not found")

        sc_stmt = select(ShortlistedCandidate).where(ShortlistedCandidate.advertisement_id == advertisement_id)
        all_scs = (await db.execute(sc_stmt)).scalars().all()
        
        if not all_scs:
            self._raise_error(400, "NO_CANDIDATES", "No candidates shortlisted for this round")

        # Check if any letters have been issued. If so, block re-ranking to preserve integrity.
        letters_count = (await db.execute(
            select(func.count(AppointmentLetter.id))
            .where(AppointmentLetter.selection_result_id.in_(
                select(SelectionResult.id).where(SelectionResult.advertisement_id == advertisement_id)
            ))
        )).scalar_one()
        
        if letters_count > 0:
            self._raise_error(
                400, 
                "RANKING_LOCKED", 
                "Cannot re-generate rankings because appointment letters have already been issued. Please cancel issued letters first if you need to re-rank."
            )

        ranking_inputs = []
        for sc in all_scs:
            marks = (await db.execute(select(InterviewMarks).where(and_(InterviewMarks.advertisement_id == advertisement_id, InterviewMarks.application_id == sc.application_id)))).scalars().first()
            if not marks:
                continue
            
            cand = (await db.execute(select(Candidate).where(Candidate.id == sc.candidate_id))).scalars().first()
            qual = (await db.execute(select(CandidateQualification).where(and_(CandidateQualification.candidate_id == sc.candidate_id, CandidateQualification.is_highest == True)))).scalars().first()
            
            exp_rows = (await db.execute(select(CandidateExperience).where(and_(CandidateExperience.candidate_id == sc.candidate_id, CandidateExperience.experience_type == "TEACHING")))).scalars().all()
            total_exp = 0.0
            for e in exp_rows:
                end = e.to_date or datetime.now().date()
                total_exp += (end - e.from_date).days / 365.25
                
            pub_count = (await db.execute(select(ApplicationDocument).where(and_(ApplicationDocument.application_id == sc.application_id, ApplicationDocument.document_type == "PUBLICATION_PROOF")))).scalars().all()

            ranking_inputs.append({
                "application_id": str(sc.application_id),
                "candidate_id": str(sc.candidate_id),
                "full_name": cand.full_name,
                "category": cand.category,
                "highest_degree": qual.degree if qual else "N/A",
                "marks_percentage": float(qual.percentage) if qual and qual.percentage else 0.0,
                "teaching_experience_years": float(total_exp),
                "interview_total": float(marks.interview_total),
                "publication_count": len(pub_count)
            })

        if not ranking_inputs:
            self._raise_error(400, "NO_CANDIDATES_WITH_MARKS", "No candidates have interview marks entered")

        from app.models.institution import Course
        Course_obj = (await db.execute(select(Course).where(Course.id == ad.course_id))).scalars().first()
        
        vacancy_count = ad.vacancy_count
        if ad.assessment and ad.assessment.confirmed_vacancy:
            vacancy_count = ad.assessment.confirmed_vacancy

        # Fetch rankings from LLM
        payload = {
            "vacancy_count": vacancy_count,
            "candidates": ranking_inputs
        }
        
        llm_response = await self.ai_service.generate_ai_rankings(payload)
        ranked_candidates = llm_response.get("rankings", [])
        
        if not ranked_candidates:
            self._raise_error(500, "AI_GENERATION_FAILED", "AI failed to generate candidate rankings.")

        await db.execute(delete(CandidateScore).where(CandidateScore.advertisement_id == advertisement_id))
        await db.execute(delete(SelectionResult).where(SelectionResult.advertisement_id == advertisement_id))
        await db.execute(delete(VacancyAnomaly).where(VacancyAnomaly.advertisement_id == advertisement_id))

        for rc in ranked_candidates:
            db.add(CandidateScore(
                advertisement_id=advertisement_id,
                application_id=UUID(rc["application_id"]),
                candidate_id=UUID(rc["candidate_id"]),
                institution_id=ad.institution_id,
                qualification_score=0,
                experience_score=0,
                interview_score=0,
                publication_score=0,
                reservation_tiebreaker=0,
                final_score=Decimal(str(rc["final_score"])),
                rank=rc["rank"],
                score_breakdown={"reason": rc.get("reason", "")}
            ))
            db.add(SelectionResult(
                advertisement_id=advertisement_id,
                application_id=UUID(rc["application_id"]),
                candidate_id=UUID(rc["candidate_id"]),
                institution_id=ad.institution_id,
                course_id=ad.course_id,
                academic_year=ad.academic_year,
                rank=rc["rank"],
                final_score=Decimal(str(rc["final_score"])),
                result_status=rc["result_status"],
                waitlist_position=rc.get("waitlist_position"),
                status=FinalResultStatus.DRAFT.value
            ))

        await db.execute(update(InterviewMarks).where(InterviewMarks.advertisement_id == advertisement_id).values(is_locked=True))
        
        # We don't have deterministic weights anymore for the analysis since we used an LLM
        # But we still run the AI selection analysis for dashboard insights
        ai_analysis = await self.ai_service.evaluate_ranking_quality(
            ranked_rows=ranked_candidates,
            candidate_inputs=ranking_inputs,
            scoring_weights={},
        )

        await self._write_audit(db, "Advertisement", advertisement_id, "GENERATE_RANKING", current_user.id)
        await db.commit()
        return {"rankings": ranked_candidates, "ai_analysis": ai_analysis}

    async def get_ranked_list(self, db: AsyncSession, advertisement_id: UUID) -> List[Any]:
        stmt = (
            select(SelectionResult, Candidate.full_name)
            .join(Candidate, Candidate.id == SelectionResult.candidate_id)
            .where(SelectionResult.advertisement_id == advertisement_id)
            .order_by(SelectionResult.rank.asc())
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            return []

        candidate_ids = [sr.candidate_id for sr, _ in rows]
        app_ids = [sr.application_id for sr, _ in rows]

        scores_stmt = select(CandidateScore).where(
            and_(CandidateScore.advertisement_id == advertisement_id, CandidateScore.application_id.in_(app_ids))
        )
        scores = (await db.execute(scores_stmt)).scalars().all()
        score_map = {s.application_id: s for s in scores}

        quals_stmt = select(CandidateQualification).where(
            and_(CandidateQualification.candidate_id.in_(candidate_ids), CandidateQualification.is_highest.is_(True))
        )
        quals = (await db.execute(quals_stmt)).scalars().all()
        qual_map = {q.candidate_id: q for q in quals}

        exps_stmt = select(CandidateExperience).where(
            and_(CandidateExperience.candidate_id.in_(candidate_ids), CandidateExperience.experience_type == "TEACHING")
        )
        exps = (await db.execute(exps_stmt)).scalars().all()
        exp_map: Dict[UUID, List[CandidateExperience]] = {}
        for e in exps:
            exp_map.setdefault(e.candidate_id, []).append(e)

        results = []
        for sr, name in rows:
            score = score_map.get(sr.application_id)
            qual = qual_map.get(sr.candidate_id)
            candidate_exps = exp_map.get(sr.candidate_id, [])
            
            total_exp = 0.0
            for e in candidate_exps:
                end = e.to_date or datetime.now().date()
                total_exp += (end - e.from_date).days / 365.25

            results.append({
                "rank": sr.rank,
                "candidate_name": name,
                "application_id": sr.application_id,
                "final_score": sr.final_score,
                "result_status": sr.result_status,
                "waitlist_position": sr.waitlist_position,
                "score_breakdown": score.score_breakdown if score else {},
                "qualification": qual.degree if qual else "N/A",
                "experience_years": round(total_exp, 1)
            })
        return results

    async def confirm_selection(self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: ConfirmSelectionRequest):
        results = (await db.execute(select(SelectionResult).where(SelectionResult.advertisement_id == advertisement_id))).scalars().all()
        if not results:
             self._raise_error(400, "NO_RANKINGS", "No rankings found to confirm")
             
        stmt_check = select(SelectionResult).where(and_(SelectionResult.advertisement_id == advertisement_id, SelectionResult.result_status == SelectionResultStatus.SELECTED.value))
        selected = (await db.execute(stmt_check)).scalars().all()
        if not selected:
             self._raise_error(400, "NO_SELECTED_CANDIDATE", "Cannot confirm results without any SELECTED candidate")

        await db.execute(
            update(SelectionResult)
            .where(SelectionResult.advertisement_id == advertisement_id)
            .values(
                status=FinalResultStatus.CONFIRMED.value,
                confirmed_by=current_user.id,
                confirmed_at=func.now()
            )
        )

        for res in results:
            app_status = ApplicationStatus.REJECTED.value
            if res.result_status == SelectionResultStatus.SELECTED.value:
                app_status = ApplicationStatus.SHORTLISTED.value
            
            await db.execute(
                update(Application)
                .where(Application.id == res.application_id)
                .values(status=app_status)
            )

        await self._write_audit(db, "Advertisement", advertisement_id, "CONFIRM_RESULTS", current_user.id, new_value={"remarks": req.remarks})
        await db.commit()
        
        counts = {
            "selected_count": len([r for r in results if r.result_status == SelectionResultStatus.SELECTED.value]),
            "waitlisted_count": len([r for r in results if r.result_status == SelectionResultStatus.WAITLISTED.value]),
            "rejected_count": len([r for r in results if r.result_status == SelectionResultStatus.REJECTED.value])
        }
        return counts

    async def get_final_results(self, db: AsyncSession, advertisement_id: UUID) -> Dict[str, List[Any]]:
        stmt = (
            select(SelectionResult, Candidate.full_name, Application.application_number)
            .join(Application, Application.id == SelectionResult.application_id)
            .join(Candidate, Candidate.id == SelectionResult.candidate_id)
            .where(and_(Application.advertisement_id == advertisement_id, SelectionResult.status == FinalResultStatus.CONFIRMED.value))
            .order_by(SelectionResult.rank.asc())
        )
        rows = (await db.execute(stmt)).all()
        
        grouped = {"SELECTED": [], "WAITLISTED": [], "REJECTED": []}
        for sr, name, app_num in rows:
            grouped[sr.result_status].append({
                "id": str(sr.id),
                "candidate_name": name,
                "rank": sr.rank,
                "final_score": float(sr.final_score),
                "application_number": app_num,
                "waitlist_position": sr.waitlist_position
            })
        return grouped

    async def run_ai_selection_analysis(self, db: AsyncSession, advertisement_id: UUID) -> Dict[str, Any]:
        ranked_list = await self.get_ranked_list(db, advertisement_id)
        if not ranked_list:
            self._raise_error(400, "NO_RANKINGS", "Generate rankings before running AI analysis")

        masked_candidates = []
        id_mapping = {}
        for i, row in enumerate(ranked_list[:20]):
            mask_id = f"CAND-{i+1:03d}"
            id_mapping[mask_id] = str(row["application_id"])
            
            masked_candidates.append({
                "id": mask_id,
                "qualification": row["qualification"],
                "experience_years": row["experience_years"],
                "interview_score": row["score_breakdown"].get("interview", {}).get("raw_score", 0),
                "final_score": row["final_score"],
                "original_rank": row["rank"]
            })

        payload = {
            "candidates": masked_candidates,
            "ranking": [c["id"] for c in masked_candidates]
        }
        ai_output = await self.ai_service.analyze_selection(payload)

        unmasked_suggestions = []
        for sug in ai_output.get("ranking_suggestions", []):
            mask_id = sug.get("application_id")
            if mask_id in id_mapping:
                sug["application_id"] = id_mapping[mask_id]
                unmasked_suggestions.append(sug)
        
        ai_output["ranking_suggestions"] = unmasked_suggestions

        return {
            "system_ranking": ranked_list[:20],
            "ai_analysis": ai_output
        }

    async def get_selection_dashboard(self, db: AsyncSession, advertisement_id: UUID) -> Dict[str, Any]:
        # 1. Fetch Basic Recruitment Stats
        ad = (await db.execute(select(Advertisement).where(Advertisement.id == advertisement_id))).scalars().first()
        if not ad:
            self._raise_error(404, "ADVERTISEMENT_NOT_FOUND", "Advertisement not found")

        total_apps = (await db.execute(select(func.count(Application.id)).where(Application.advertisement_id == advertisement_id))).scalar() or 0
        shortlisted_count = (await db.execute(select(func.count(ShortlistedCandidate.id)).where(ShortlistedCandidate.advertisement_id == advertisement_id))).scalar() or 0
        marked_count = (await db.execute(select(func.count(InterviewMarks.id)).where(InterviewMarks.advertisement_id == advertisement_id))).scalar() or 0

        # 2. Try to fetch rankings
        ranked_list = await self.get_ranked_list(db, advertisement_id)
        
        distribution = [
            {"range": "0-40", "count": 0},
            {"range": "40-70", "count": 0},
            {"range": "70-100", "count": 0}
        ]
        
        bias_flags = []
        insights = ["Generate rankings to see AI-powered selection insights."]
        top_candidates = []

        if ranked_list:
            top_candidates = ranked_list[:10]
            for r in ranked_list:
                score = float(r["final_score"])
                if score < 40: distribution[0]["count"] += 1
                elif score < 70: distribution[1]["count"] += 1
                else: distribution[2]["count"] += 1
            
            try:
                ai_data = await self.run_ai_selection_analysis(db, advertisement_id)
                bias_flags = ai_data["ai_analysis"].get("bias_flags", [])
                insights = ai_data["ai_analysis"].get("insights", [])
            except Exception:
                # Fallback if AI analysis fails but rankings exist
                pass
        
        return {
            "status": ad.status,
            "total_applications": total_apps,
            "shortlisted_count": shortlisted_count,
            "marked_count": marked_count,
            "top_candidates": top_candidates,
            "score_distribution": distribution,
            "bias_flags": bias_flags,
            "insights": insights
        }

    async def create_ai_snapshot(self, db: AsyncSession, current_user: User, advertisement_id: UUID) -> Dict[str, Any]:
        ad = (await db.execute(select(Advertisement).where(Advertisement.id == advertisement_id))).scalars().first()
        if not ad:
            self._raise_error(404, "NOT_FOUND", "Advertisement not found")

        ai_data = await self.run_ai_selection_analysis(db, advertisement_id)
        
        snapshot = SelectionAISnapshot(
            advertisement_id=advertisement_id,
            institution_id=ad.institution_id,
            analysis_data=ai_data["ai_analysis"],
            snapshot_data={},
            created_by=current_user.id
        )
        db.add(snapshot)
        await self._write_audit(db, "SelectionAISnapshot", snapshot.id, "CREATE_SNAPSHOT", current_user.id)
        await db.commit()
        await db.refresh(snapshot)
        
        return {"status": "success", "snapshot_id": snapshot.id}

    async def get_selection_results(self, db: AsyncSession, institution_id: int | None, status: str | None, result_status: str | None) -> List[dict]:
        filters = []
        if institution_id:
            filters.append(SelectionResult.institution_id == institution_id)
        if status:
            filters.append(SelectionResult.status == status)
        if result_status:
            filters.append(SelectionResult.result_status == result_status)
            
        from app.models.institution import Course
        stmt = (
            select(SelectionResult, Candidate.full_name, Application.application_number, Course.name.label("course_name"))
            .join(Candidate, Candidate.id == SelectionResult.candidate_id)
            .join(Application, Application.id == SelectionResult.application_id)
            .join(Course, Course.id == SelectionResult.course_id)
            .where(and_(*filters))
            .order_by(SelectionResult.created_at.desc())
        )
        rows = (await db.execute(stmt)).all()
        
        return [
            {
                "id": sr.id,
                "candidate_name": name,
                "course_name": cname,
                "application_number": app_num,
                "final_score": float(sr.final_score),
                "rank": sr.rank,
                "result_status": sr.result_status,
                "status": sr.status,
                "created_at": sr.created_at
            }
            for sr, name, app_num, cname in rows
        ]
