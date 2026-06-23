from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.candidate.schemas import (
    CandidateExperienceResponse,
    CandidateProfileResponse,
    CandidateQualificationResponse,
    CandidateProfileRequest,
    ExperienceBulkRequest,
    QualificationBulkRequest,
)
from app.modules.candidate.service import CandidateService


class CandidateController:
    def __init__(self) -> None:
        self.service = CandidateService()

    async def upsert_profile(self, db: AsyncSession, current_user: User, req: CandidateProfileRequest):
        data = await self.service.create_or_update_profile(db, current_user, req)
        payload = CandidateProfileResponse.model_validate(data, from_attributes=True).model_dump()
        return {"status": "success", "data": payload}

    async def get_profile(self, db: AsyncSession, current_user: User):
        data = await self.service.get_profile(db, current_user)
        if not data:
            return {"status": "success", "data": None}
        payload = CandidateProfileResponse.model_validate(data, from_attributes=True).model_dump()
        return {"status": "success", "data": payload}

    async def add_qualifications(self, db: AsyncSession, current_user: User, req: QualificationBulkRequest):
        data = await self.service.add_qualifications(db, current_user, req)
        payload = [
            CandidateQualificationResponse.model_validate(item, from_attributes=True).model_dump()
            for item in data
        ]
        return {"status": "success", "data": payload}

    async def add_experience(self, db: AsyncSession, current_user: User, req: ExperienceBulkRequest):
        data = await self.service.add_experience(db, current_user, req)
        payload = [CandidateExperienceResponse.model_validate(item, from_attributes=True).model_dump() for item in data]
        return {"status": "success", "data": payload}

    async def get_profile_by_id(self, db: AsyncSession, candidate_id: str):
        data = await self.service.get_profile_by_candidate_id(db, candidate_id)
        payload = CandidateProfileResponse.model_validate(data, from_attributes=True).model_dump()
        return {"status": "success", "data": payload}
