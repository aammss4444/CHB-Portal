from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.modules.selection.service import SelectionService
from app.modules.selection.schemas import (
    ShortlistRequest,
    AttendanceRequest,
    InterviewMarksRequest,
    InterviewMarksUpdateRequest,
    ConfirmSelectionRequest
)

class SelectionController:
    def __init__(self):
        self.service = SelectionService()

    async def shortlist_candidates(self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: ShortlistRequest):
        await self.service.shortlist_candidates(db, current_user, advertisement_id, req)
        return {"status": "success", "message": "Candidates shortlisted successfully"}

    async def get_shortlisted(self, db: AsyncSession, advertisement_id: UUID):
        data = await self.service.get_shortlisted(db, advertisement_id)
        return {"status": "success", "data": data}

    async def mark_attendance(self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: AttendanceRequest):
        await self.service.mark_attendance(db, current_user, advertisement_id, req)
        return {"status": "success", "message": "Attendance updated successfully"}

    async def enter_marks(self, db: AsyncSession, current_user: User, req: InterviewMarksRequest):
        marks = await self.service.enter_marks(db, current_user, req)
        return {"status": "success", "data": {"mark_id": marks.id, "interview_total": float(marks.interview_total)}}

    async def update_marks(self, db: AsyncSession, current_user: User, mark_id: UUID, req: InterviewMarksUpdateRequest):
        marks = await self.service.update_marks(db, current_user, mark_id, req)
        return {"status": "success", "data": {"mark_id": marks.id, "interview_total": float(marks.interview_total)}}

    async def generate_rankings(self, db: AsyncSession, current_user: User, advertisement_id: UUID):
        result = await self.service.generate_rankings(db, current_user, advertisement_id)
        return {
            "status": "success",
            "data": result["rankings"],
            "ai_analysis": result["ai_analysis"],
        }

    async def get_ranked_list(self, db: AsyncSession, advertisement_id: UUID):
        data = await self.service.get_ranked_list(db, advertisement_id)
        return {"status": "success", "data": data}

    async def confirm_selection(self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: ConfirmSelectionRequest):
        counts = await self.service.confirm_selection(db, current_user, advertisement_id, req)
        return {"status": "success", "data": counts, "message": "Selection results confirmed and locked."}

    async def get_final_results(self, db: AsyncSession, advertisement_id: UUID):
        grouped = await self.service.get_final_results(db, advertisement_id)
        return {"status": "success", "data": grouped}

    async def run_ai_selection_analysis(self, db: AsyncSession, advertisement_id: UUID):
        result = await self.service.run_ai_selection_analysis(db, advertisement_id)
        return {"status": "success", "data": result}

    async def get_selection_dashboard(self, db: AsyncSession, advertisement_id: UUID):
        result = await self.service.get_selection_dashboard(db, advertisement_id)
        return {"status": "success", "data": result}

    async def create_ai_snapshot(self, db: AsyncSession, current_user: User, advertisement_id: UUID):
        result = await self.service.create_ai_snapshot(db, current_user, advertisement_id)
        return result

    async def get_all_results(self, db: AsyncSession, institution_id: int | None, status: str | None, result_status: str | None):
        items = await self.service.get_selection_results(db, institution_id, status, result_status)
        return {"status": "success", "items": items}
