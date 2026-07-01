from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.appointment.schemas import (
    AppointmentGenerateRequest,
    AppointmentRespondRequest,
    AppointmentUpdateRequest,
)
from app.modules.appointment.service import AppointmentService


class AppointmentController:
    def __init__(self) -> None:
        self.service = AppointmentService()

    async def generate(self, db: AsyncSession, current_user: User, req: AppointmentGenerateRequest):
        letter = await self.service.generate_letter(db, current_user, req)
        data = await self.service.get_letter(db, current_user, letter.id)
        return {"status": "success", "data": data}

    async def get(self, db: AsyncSession, current_user: User, appointment_id: UUID):
        data = await self.service.get_letter(db, current_user, appointment_id)
        return {"status": "success", "data": data}

    async def update(self, db: AsyncSession, current_user: User, appointment_id: UUID, req: AppointmentUpdateRequest):
        letter = await self.service.update_letter(db, current_user, appointment_id, req)
        data = await self.service.get_letter(db, current_user, letter.id)
        return {"status": "success", "data": data}

    async def submit(self, db: AsyncSession, current_user: User, appointment_id: UUID):
        # In the new workflow, submit by Principal directly issues it to Candidate
        letter = await self.service.submit_letter_directly(db, current_user, appointment_id)
        return {"status": "success", "data": {"appointment_id": letter.id, "status": letter.status}}

    async def respond(
        self,
        db: AsyncSession,
        current_user: User,
        appointment_id: UUID,
        req: AppointmentRespondRequest,
        ip_address: str | None,
    ):
        letter = await self.service.respond_letter(db, current_user, appointment_id, req, ip_address)
        return {"status": "success", "data": {"appointment_id": letter.id, "status": letter.status}}

    async def list_institution(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: int,
        academic_year: str | None,
        status: str | None,
        course_id: int | None,
        page: int,
        size: int,
    ):
        data = await self.service.list_institution_letters(
            db, current_user, institution_id, academic_year, status, course_id, page, size
        )
        return {"status": "success", "data": data}

    async def delete(self, db: AsyncSession, current_user: User, appointment_id: UUID):
        await self.service.delete_letter(db, current_user, appointment_id)
        return {"status": "success", "message": "Appointment letter deleted successfully"}

    async def list_candidate(self, db: AsyncSession, current_user: User):
        data = await self.service.list_candidate_letters(db, current_user)
        return {"status": "success", "data": data}
