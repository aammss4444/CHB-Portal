from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.selection_round import SelectionRound, SelectionRoundType, SelectionRoundStatus
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

from app.modules.selection.schemas import (
    SelectionRoundCreateRequest,
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
        # Convert UUID to int for global audit log compatibility if needed
        # Existing convention uses ad.id.int % 2147483647
        eid = str(entity_id)
        db.add(AuditLog(
            entity_name=entity,
            entity_id=eid,
            action=action,
            user_id=user_id,
            old_value=old_value,
            new_value=new_value
        ))

    async def create_round(self, db: AsyncSession, current_user: User, req: SelectionRoundCreateRequest) -> SelectionRound:
        # Gate: Ad must be published
        ad = (await db.execute(select(Advertisement).where(Advertisement.id == req.advertisement_id))).scalars().first()
        if not ad or ad.status != AdvertisementStatus.PUBLISHED.value:
            self._raise_error(400, "ADVERTISEMENT_NOT_PUBLISHED", "Advertisement must be PUBLISHED before scheduling rounds")

        from app.dependencies.institution_scope import verify_institution_access
        await verify_institution_access(ad.institution_id, current_user)

        # Gate: No duplicate round_type
        existing = (await db.execute(
            select(SelectionRound).where(
                and_(
                    SelectionRound.advertisement_id == req.advertisement_id,
                    SelectionRound.round_type == req.round_type
                )
            )
        )).scalars().first()
        if existing:
            self._raise_error(409, "ROUND_ALREADY_EXISTS", f"A {req.round_type} round already exists for this advertisement")

        round_obj = SelectionRound(
            advertisement_id=req.advertisement_id,
            institution_id=ad.institution_id,
            course_id=ad.course_id,
            academic_year=ad.academic_year,
            round_type=req.round_type,
            scheduled_date=req.scheduled_date,
            status=SelectionRoundStatus.SCHEDULED.value,
            created_by=current_user.id
        )
        db.add(round_obj)
        await db.flush()
        await self._write_audit(db, "SelectionRound", round_obj.id, "CREATE_ROUND", current_user.id, new_value=req.model_dump(mode="json"))
        await db.commit()
        return round_obj

    async def shortlist_candidates(self, db: AsyncSession, current_user: User, round_id: UUID, req: ShortlistRequest):
        round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
        if not round_obj:
            self._raise_error(404, "ROUND_NOT_FOUND", "Round not found")
        
        if round_obj.status == SelectionRoundStatus.COMPLETED.value:
             self._raise_error(400, "ROUND_COMPLETED", "Cannot shortlist for a completed round")

        # Bulk fetch applications
        stmt = select(Application).where(Application.id.in_(req.application_ids))
        apps = (await db.execute(stmt)).scalars().all()
        app_map = {app.id: app for app in apps}

        # Bulk fetch existing shortlist entries to avoid duplicates
        existing_stmt = select(ShortlistedCandidate.application_id).where(ShortlistedCandidate.round_id == round_id)
        existing_ids = set((await db.execute(existing_stmt)).scalars().all())

        for app_id in req.application_ids:
            app = app_map.get(app_id)
            if not app or app.advertisement_id != round_obj.advertisement_id:
                continue
            if app.status != ApplicationStatus.SUBMITTED.value:
                continue
            if app_id in existing_ids:
                continue

            db.add(ShortlistedCandidate(
                round_id=round_id,
                application_id=app_id,
                candidate_id=app.candidate_id,
                shortlisted_by=current_user.id,
                shortlist_remarks=req.remarks
            ))
            app.status = ApplicationStatus.UNDER_REVIEW.value

        round_obj.status = SelectionRoundStatus.IN_PROGRESS.value
        await self._write_audit(db, "SelectionRound", round_id, "SHORTLIST_CANDIDATES", current_user.id)
        await db.commit()

    async def get_shortlisted(self, db: AsyncSession, round_id: UUID) -> List[dict]:
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
                InterviewMarks.round_id == round_id, 
                InterviewMarks.application_id == ShortlistedCandidate.application_id
            ))
            .where(ShortlistedCandidate.round_id == round_id)
        )
        rows = (await db.execute(stmt)).all()
        
        results = []
        for sc, name, app_num, int_total in rows:
            # Get qualification
            qual = (await db.execute(select(CandidateQualification).where(
                and_(CandidateQualification.candidate_id == sc.candidate_id, CandidateQualification.is_highest == True)
            ))).scalars().first()
            
            # Get experience
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

    async def mark_attendance(self, db: AsyncSession, current_user: User, round_id: UUID, req: AttendanceRequest):
        round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
        if not round_obj or round_obj.status != SelectionRoundStatus.IN_PROGRESS.value:
            self._raise_error(400, "ROUND_NOT_IN_PROGRESS", "Attendance can only be marked for IN_PROGRESS rounds")

        for item in req.attendance:
            await db.execute(
                update(ShortlistedCandidate)
                .where(and_(ShortlistedCandidate.round_id == round_id, ShortlistedCandidate.application_id == item.application_id))
                .values(is_present=item.is_present)
            )
        
        await self._write_audit(db, "SelectionRound", round_id, "MARK_ATTENDANCE", current_user.id)
        await db.commit()

    async def enter_marks(self, db: AsyncSession, current_user: User, req: InterviewMarksRequest) -> InterviewMarks:
        round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == req.round_id))).scalars().first()
        if not round_obj or round_obj.status != SelectionRoundStatus.IN_PROGRESS.value:
            self._raise_error(400, "ROUND_NOT_IN_PROGRESS", "Marks can only be entered for IN_PROGRESS rounds")

        # Gate: Present check
        sc = (await db.execute(select(ShortlistedCandidate).where(
            and_(ShortlistedCandidate.round_id == req.round_id, ShortlistedCandidate.application_id == req.application_id)
        ))).scalars().first()
        if not sc or not sc.is_present:
            self._raise_error(400, "CANDIDATE_ABSENT", "Cannot enter marks for absent candidate")

        # Gate: Duplicate check
        existing = (await db.execute(select(InterviewMarks).where(
            and_(InterviewMarks.round_id == req.round_id, InterviewMarks.application_id == req.application_id)
        ))).scalars().first()
        if existing:
             self._raise_error(409, "MARKS_ALREADY_ENTERED", "Marks already entered. Use PUT to update.")

        total = (req.subject_knowledge + req.teaching_aptitude + req.communication_skills + req.overall_impression) / 4
        
        marks = InterviewMarks(
            round_id=req.round_id,
            application_id=req.application_id,
            candidate_id=req.candidate_id,
            institution_id=round_obj.institution_id,
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

    async def generate_rankings(self, db: AsyncSession, current_user: User, round_id: UUID) -> Dict[str, Any]:
        round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
        if not round_obj or round_obj.status != SelectionRoundStatus.IN_PROGRESS.value:
            self._raise_error(400, "ROUND_NOT_IN_PROGRESS", "Ranking can only be generated for IN_PROGRESS rounds")

        # 1. Fetch present candidates
        present_stmt = select(ShortlistedCandidate).where(and_(ShortlistedCandidate.round_id == round_id, ShortlistedCandidate.is_present == True))
        present_scs = (await db.execute(present_stmt)).scalars().all()
        
        if not present_scs:
            self._raise_error(400, "NO_CANDIDATES_PRESENT", "No candidates present for interview")

        # 2. Check if all have marks
        ranking_inputs = []
        missing_marks = []
        for sc in present_scs:
            marks = (await db.execute(select(InterviewMarks).where(and_(InterviewMarks.round_id == round_id, InterviewMarks.application_id == sc.application_id)))).scalars().first()
            if not marks:
                missing_marks.append(str(sc.application_id))
                continue
            
            # Fetch candidate info for engine
            cand = (await db.execute(select(Candidate).where(Candidate.id == sc.candidate_id))).scalars().first()
            qual = (await db.execute(select(CandidateQualification).where(and_(CandidateQualification.candidate_id == sc.candidate_id, CandidateQualification.is_highest == True)))).scalars().first()
            
            exp_rows = (await db.execute(select(CandidateExperience).where(and_(CandidateExperience.candidate_id == sc.candidate_id, CandidateExperience.experience_type == "TEACHING")))).scalars().all()
            total_exp = 0.0
            for e in exp_rows:
                end = e.to_date or datetime.now().date()
                total_exp += (end - e.from_date).days / 365.25
                
            pub_count = (await db.execute(select(ApplicationDocument).where(and_(ApplicationDocument.application_id == sc.application_id, ApplicationDocument.document_type == "PUBLICATION_PROOF")))).scalars().all()

            ranking_inputs.append(CandidateRankingInput(
                application_id=sc.application_id,
                candidate_id=sc.candidate_id,
                full_name=cand.full_name,
                category=cand.category,
                highest_degree=qual.degree if qual else "N/A",
                teaching_experience_years=total_exp,
                interview_total=float(marks.interview_total),
                publication_count=len(pub_count)
            ))

        if missing_marks:
            self._raise_error(400, "MISSING_MARKS_FOR_CANDIDATES", f"Marks missing for: {', '.join(missing_marks)}")

        # 3. Resolve weights
        ad_stmt = select(Advertisement).options(selectinload(Advertisement.assessment)).where(Advertisement.id == round_obj.advertisement_id)
        ad = (await db.execute(ad_stmt)).scalars().first()
        
        from app.models.institution import Course
        Course = (await db.execute(select(Course).where(Course.id == round_obj.course_id))).scalars().first()
        
        vacancy_count = ad.vacancy_count
        if ad.assessment and ad.assessment.confirmed_vacancy:
            vacancy_count = ad.assessment.confirmed_vacancy

        weight_config, priority = await self.weight_service.resolve_weights(
            db, 
            round_obj.course_id, 
            Course.level if Course else "UG", 
            round_obj.advertisement_id
        )

        # 4. Run Engine
        ranked_candidates = compute_candidate_rankings(round_id, ranking_inputs, vacancy_count, weight_config)

        # 5. Save Results & Anomlies
        # Clear old if any (idempotent)
        await db.execute(delete(CandidateScore).where(CandidateScore.round_id == round_id))
        await db.execute(delete(SelectionResult).where(SelectionResult.round_id == round_id))
        await db.execute(delete(VacancyAnomaly).where(VacancyAnomaly.round_id == round_id))

        for rc in ranked_candidates:
            db.add(CandidateScore(
                round_id=round_id,
                application_id=rc.application_id,
                candidate_id=rc.candidate_id,
                institution_id=round_obj.institution_id,
                qualification_score=rc.score_breakdown["qualification"]["weighted"],
                experience_score=rc.score_breakdown["experience"]["weighted"],
                interview_score=rc.score_breakdown["interview"]["weighted"],
                publication_score=rc.score_breakdown["publication"]["weighted"],
                reservation_tiebreaker=rc.score_breakdown["reservation"]["weighted"],
                final_score=rc.final_score,
                rank=rc.rank,
                score_breakdown=rc.score_breakdown
            ))
            db.add(SelectionResult(
                round_id=round_id,
                application_id=rc.application_id,
                candidate_id=rc.candidate_id,
                institution_id=round_obj.institution_id,
                course_id=round_obj.course_id,
                academic_year=round_obj.academic_year,
                rank=rc.rank,
                final_score=rc.final_score,
                result_status=rc.result_status,
                waitlist_position=rc.waitlist_position,
                status=FinalResultStatus.DRAFT.value
            ))

        # Save anomalies (just use the list from the first ranked candidate)
        for anom in ranked_candidates[0].anomalies:
            db.add(VacancyAnomaly(
                round_id=round_id,
                anomaly_type=anom["type"],
                severity=anom["severity"],
                description=anom["message"]
            ))

        # 6. Lock Marks & Round
        await db.execute(update(InterviewMarks).where(InterviewMarks.round_id == round_id).values(is_locked=True))
        round_obj.status = SelectionRoundStatus.COMPLETED.value
        
        ai_analysis = await self.ai_service.evaluate_ranking_quality(
            ranked_rows=[rc.model_dump(mode="python") for rc in ranked_candidates],
            candidate_inputs=[ci.model_dump(mode="python") for ci in ranking_inputs],
            scoring_weights={
                "qualification_weight": float(weight_config.qualification_weight),
                "experience_weight": float(weight_config.experience_weight),
                "interview_weight": float(weight_config.interview_weight),
                "publication_weight": float(weight_config.publication_weight),
                "reservation_weight": float(weight_config.reservation_weight),
            },
        )

        await self._write_audit(db, "SelectionRound", round_id, "GENERATE_RANKING", current_user.id)
        await db.commit()
        return {"rankings": ranked_candidates, "ai_analysis": ai_analysis}

    async def get_ranked_list(self, db: AsyncSession, round_id: UUID) -> List[Any]:
        stmt = (
            select(SelectionResult, Candidate.full_name)
            .join(Candidate, Candidate.id == SelectionResult.candidate_id)
            .where(SelectionResult.round_id == round_id)
            .order_by(SelectionResult.rank.asc())
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            return []

        candidate_ids = [sr.candidate_id for sr, _ in rows]
        app_ids = [sr.application_id for sr, _ in rows]

        # Bulk fetch scores
        scores_stmt = select(CandidateScore).where(
            and_(CandidateScore.round_id == round_id, CandidateScore.application_id.in_(app_ids))
        )
        scores = (await db.execute(scores_stmt)).scalars().all()
        score_map = {s.application_id: s for s in scores}

        # Bulk fetch qualifications
        quals_stmt = select(CandidateQualification).where(
            and_(CandidateQualification.candidate_id.in_(candidate_ids), CandidateQualification.is_highest.is_(True))
        )
        quals = (await db.execute(quals_stmt)).scalars().all()
        qual_map = {q.candidate_id: q for q in quals}

        # Bulk fetch experiences
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

    async def confirm_selection(self, db: AsyncSession, current_user: User, round_id: UUID, req: ConfirmSelectionRequest):
        round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
        if not round_obj or round_obj.status != SelectionRoundStatus.COMPLETED.value:
            self._raise_error(400, "ROUND_NOT_COMPLETED", "Only completed rounds can be confirmed")

        # Gate: at least one SELECTED
        stmt_check = select(SelectionResult).where(and_(SelectionResult.round_id == round_id, SelectionResult.result_status == SelectionResultStatus.SELECTED.value))
        selected = (await db.execute(stmt_check)).scalars().all()
        if not selected:
             self._raise_error(400, "NO_SELECTED_CANDIDATE", "Cannot confirm results without any SELECTED candidate")

        # Update results
        await db.execute(
            update(SelectionResult)
            .where(SelectionResult.round_id == round_id)
            .values(
                status=FinalResultStatus.CONFIRMED.value,
                confirmed_by=current_user.id,
                confirmed_at=func.now()
            )
        )

        # Update applications
        results = (await db.execute(select(SelectionResult).where(SelectionResult.round_id == round_id))).scalars().all()
        for res in results:
            app_status = ApplicationStatus.REJECTED.value
            if res.result_status == SelectionResultStatus.SELECTED.value:
                app_status = ApplicationStatus.SHORTLISTED.value # Spec: "SELECTED or REJECTED", but existing enum is SHORTLISTED for selected ones in Step 5?
                # Actually Step 4 enum: SHORTLISTED. Let's use it.
            
            await db.execute(
                update(Application)
                .where(Application.id == res.application_id)
                .values(status=app_status)
            )

        await self._write_audit(db, "SelectionRound", round_id, "CONFIRM_RESULTS", current_user.id, new_value={"remarks": req.remarks})
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

    async def run_ai_selection_analysis(self, db: AsyncSession, round_id: UUID) -> Dict[str, Any]:
        # 1. Fetch data
        ranked_list = await self.get_ranked_list(db, round_id)
        if not ranked_list:
            self._raise_error(400, "NO_RANKINGS", "Generate rankings before running AI analysis")

        # 2. Mask PII and create mapping
        masked_candidates = []
        id_mapping = {}
        for i, row in enumerate(ranked_list[:20]):  # Limit to top 20
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

        # 3. Call AI
        payload = {
            "candidates": masked_candidates,
            "ranking": [c["id"] for c in masked_candidates]
        }
        ai_output = await self.ai_service.analyze_selection(payload)

        # 4. Unmask application IDs in suggestions
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

    async def get_selection_dashboard(self, db: AsyncSession, round_id: UUID) -> Dict[str, Any]:
        ranked_list = await self.get_ranked_list(db, round_id)
        if not ranked_list:
            self._raise_error(400, "NO_RANKINGS", "No data for dashboard")

        # Score distribution
        distribution = [
            {"range": "0-40", "count": 0},
            {"range": "40-70", "count": 0},
            {"range": "70-100", "count": 0}
        ]
        for r in ranked_list:
            score = float(r["final_score"])
            if score < 40: distribution[0]["count"] += 1
            elif score < 70: distribution[1]["count"] += 1
            else: distribution[2]["count"] += 1

        # Get the latest AI analysis (non-persistent query for dashboard)
        ai_data = await self.run_ai_selection_analysis(db, round_id)

        return {
            "top_candidates": ranked_list[:10],
            "score_distribution": distribution,
            "bias_flags": ai_data["ai_analysis"]["bias_flags"],
            "insights": ai_data["ai_analysis"]["insights"]
        }

    async def create_ai_snapshot(self, db: AsyncSession, current_user: User, round_id: UUID) -> Dict[str, Any]:
        round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
        if not round_obj:
            self._raise_error(404, "NOT_FOUND", "Round not found")

        ai_data = await self.run_ai_selection_analysis(db, round_id)
        
        snapshot = SelectionAISnapshot(
            round_id=round_id,
            institution_id=round_obj.institution_id,
            analysis_data=ai_data["ai_analysis"],
            created_by=current_user.id
        )
        db.add(snapshot)
        await self._write_audit(db, "SelectionAISnapshot", snapshot.id, "CREATE_SNAPSHOT", current_user.id)
        await db.commit()
        await db.refresh(snapshot)
        
        return {"status": "success", "snapshot_id": snapshot.id}
