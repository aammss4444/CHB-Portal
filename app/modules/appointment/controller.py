from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.appointment.schemas import (
    AppointmentApproveRequest,
    AppointmentCancelRequest,
    AppointmentGenerateRequest,
    AppointmentRespondRequest,
    AppointmentUpdateRequest,
    CredentialResponse,
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
        letter = await self.service.submit_letter(db, current_user, appointment_id)
        return {"status": "success", "data": {"appointment_id": letter.id, "status": letter.status}}

    async def approve(
        self, db: AsyncSession, current_user: User, appointment_id: UUID, req: AppointmentApproveRequest
    ):
        letter = await self.service.approve_letter(db, current_user, appointment_id, req)
        return {"status": "success", "data": {"appointment_id": letter.id, "status": letter.status}}

    async def issue(self, db: AsyncSession, current_user: User, appointment_id: UUID):
        letter = await self.service.issue_letter(db, current_user, appointment_id)
        return {
            "status": "success",
            "data": {
                "appointment_number": letter.appointment_number,
                "issued_at": letter.issued_at,
                "acceptance_deadline": letter.acceptance_deadline,
            },
        }

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

    async def cancel(
        self, db: AsyncSession, current_user: User, appointment_id: UUID, req: AppointmentCancelRequest
    ):
        letter = await self.service.cancel_letter(db, current_user, appointment_id, req.remarks)
        return {"status": "success", "data": {"appointment_id": letter.id, "status": letter.status}}

    async def credentials(self, db: AsyncSession, current_user: User, appointment_id: UUID):
        creds = await self.service.trigger_credentials(db, current_user, appointment_id)
        payload = CredentialResponse.model_validate(creds, from_attributes=True).model_dump()
        return {"status": "success", "data": payload}

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
