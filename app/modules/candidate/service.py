from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditLog
from app.models.candidate import Candidate
from app.models.candidate_experience import CandidateExperience
from app.models.candidate_qualification import CandidateQualification
from app.models.user import User
from app.modules.candidate.schemas import (
    CandidateProfileRequest,
    ExperienceBulkRequest,
    QualificationBulkRequest,
)


MOBILE_PATTERN = re.compile(r"^(?:\+91[-.\s]?)?[6-9]\d{9}$")


class CandidateService:
    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _entity_id_from_uuid(value: UUID) -> str:
        return str(value)

    async def _write_audit(
        self,
        db: AsyncSession,
        entity_name: str,
        entity_id: str,
        action: str,
        user_id: int,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
    ) -> None:
        db.add(
            AuditLog(
                entity_name=entity_name,
                entity_id=entity_id,
                action=action,
                user_id=user_id,
                old_value=old_value,
                new_value=new_value,
            )
        )

    async def _get_candidate_by_user(self, db: AsyncSession, user_id: int) -> Optional[Candidate]:
        stmt = (
            select(Candidate)
            .where(Candidate.user_id == user_id)
            .options(
                selectinload(Candidate.qualifications),
                selectinload(Candidate.experiences),
            )
        )
        return (await db.execute(stmt)).scalars().first()

    async def _get_candidate_or_404(self, db: AsyncSession, user_id: int) -> Candidate:
        candidate = await self._get_candidate_by_user(db, user_id)
        if not candidate:
            self._raise_error(404, "UNAUTHORIZED_ACCESS", "Candidate profile not found for current user")
        return candidate

    @staticmethod
    def _compute_profile_complete(req: CandidateProfileRequest) -> bool:
        required = [
            req.full_name,
            req.date_of_birth,
            req.gender,
            req.category,
            req.mobile,
            req.email,
            req.address,
        ]
        return all(v is not None and str(v).strip() != "" for v in required)

    @staticmethod
    def _ensure_min_age_21(dob: date) -> None:
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 21:
            CandidateService._raise_error(
                400,
                "PROFILE_INCOMPLETE",
                "Candidate must be at least 21 years old.",
            )

    async def _ensure_profile_editable(self, db: AsyncSession, candidate_id: UUID) -> None:
        active_app = (
            await db.execute(
                select(Application.application_number).where(
                    and_(
                        Application.candidate_id == candidate_id,
                        Application.status.notin_(
                            [ApplicationStatus.DRAFT.value, ApplicationStatus.WITHDRAWN.value]
                        ),
                    )
                )
            )
        ).first()
        if active_app:
            self._raise_error(
                403,
                "PROFILE_LOCKED",
                f"Profile cannot be edited while application {active_app.application_number} is active.",
            )

    async def create_or_update_profile(
        self, db: AsyncSession, current_user: User, req: CandidateProfileRequest
    ) -> Candidate:
        if not MOBILE_PATTERN.match(req.mobile):
            self._raise_error(400, "PROFILE_INCOMPLETE", "Mobile number must be a valid 10 digit Indian number.")

        self._ensure_min_age_21(req.date_of_birth)

        candidate = await self._get_candidate_by_user(db, current_user.id)
        if candidate:
            await self._ensure_profile_editable(db, candidate.id)

        aadhar_hash = None
        if req.aadhar_number:
            aadhar_hash = hashlib.sha256(req.aadhar_number.strip().encode("utf-8")).hexdigest()

        profile_complete = self._compute_profile_complete(req)

        if not candidate:
            candidate = Candidate(
                user_id=current_user.id,
                full_name=req.full_name,
                father_name=req.father_name,
                date_of_birth=req.date_of_birth,
                gender=req.gender.value,
                category=req.category.value,
                religion=req.religion,
                nationality=req.nationality,
                mobile=req.mobile,
                email=req.email,
                address=req.address,
                district=req.district,
                state=req.state,
                pincode=req.pincode,
                aadhar_number=aadhar_hash,
                is_profile_complete=profile_complete,
            )
            db.add(candidate)
            await db.flush()
            await self._write_audit(
                db,
                "Candidate",
                self._entity_id_from_uuid(candidate.id),
                "UPSERT_PROFILE",
                current_user.id,
                new_value={"is_profile_complete": profile_complete},
            )
        else:
            old_values = {
                "full_name": candidate.full_name,
                "mobile": candidate.mobile,
                "email": candidate.email,
                "is_profile_complete": candidate.is_profile_complete,
            }
            candidate.full_name = req.full_name
            candidate.father_name = req.father_name
            candidate.date_of_birth = req.date_of_birth
            candidate.gender = req.gender.value
            candidate.category = req.category.value
            candidate.religion = req.religion
            candidate.nationality = req.nationality
            candidate.mobile = req.mobile
            candidate.email = req.email
            candidate.address = req.address
            candidate.district = req.district
            candidate.state = req.state
            candidate.pincode = req.pincode
            if aadhar_hash:
                candidate.aadhar_number = aadhar_hash
            candidate.is_profile_complete = profile_complete
            await self._write_audit(
                db,
                "Candidate",
                self._entity_id_from_uuid(candidate.id),
                "UPSERT_PROFILE",
                current_user.id,
                old_value=old_values,
                new_value={"is_profile_complete": profile_complete},
            )

        await db.commit()
        refreshed = await self._get_candidate_or_404(db, current_user.id)
        return refreshed

    async def get_profile(self, db: AsyncSession, current_user: User) -> Optional[Candidate]:
        return await self._get_candidate_by_user(db, current_user.id)

    async def add_qualifications(
        self, db: AsyncSession, current_user: User, req: QualificationBulkRequest
    ) -> list[CandidateQualification]:
        candidate = await self._get_candidate_or_404(db, current_user.id)
        await self._ensure_profile_editable(db, candidate.id)

        current_year = date.today().year
        new_highest = sum(1 for item in req.qualifications if item.is_highest)
        existing_highest = (
            await db.execute(
                select(func.count(CandidateQualification.id)).where(
                    and_(
                        CandidateQualification.candidate_id == candidate.id,
                        CandidateQualification.is_highest.is_(True),
                    )
                )
            )
        ).scalar_one()
        if new_highest + existing_highest > 1:
            self._raise_error(400, "PROFILE_INCOMPLETE", "Only one qualification can be marked as highest.")

        created: list[CandidateQualification] = []
        for item in req.qualifications:
            if item.year_of_passing and item.year_of_passing > current_year:
                self._raise_error(400, "PROFILE_INCOMPLETE", "year_of_passing cannot be in the future.")
            if item.percentage is not None and (item.percentage < 0 or item.percentage > 100):
                self._raise_error(400, "PROFILE_INCOMPLETE", "percentage must be between 0 and 100.")

            qualification = CandidateQualification(
                candidate_id=candidate.id,
                degree=item.degree,
                specialization=item.specialization,
                university=item.university,
                year_of_passing=item.year_of_passing,
                percentage=item.percentage,
                is_highest=item.is_highest,
            )
            db.add(qualification)
            created.append(qualification)

        await db.flush()
        await self._write_audit(
            db,
            "CandidateQualification",
            self._entity_id_from_uuid(candidate.id),
            "ADD_QUALIFICATIONS",
            current_user.id,
            new_value={"count": len(created)},
        )
        await db.commit()
        return created

    async def add_experience(
        self, db: AsyncSession, current_user: User, req: ExperienceBulkRequest
    ) -> list[CandidateExperience]:
        candidate = await self._get_candidate_or_404(db, current_user.id)
        await self._ensure_profile_editable(db, candidate.id)

        created: list[CandidateExperience] = []
        for item in req.experiences:
            if item.is_current and item.to_date is not None:
                self._raise_error(400, "PROFILE_INCOMPLETE", "to_date must be null when is_current is true.")
            if item.from_date and item.to_date and item.from_date >= item.to_date:
                self._raise_error(400, "PROFILE_INCOMPLETE", "from_date must be before to_date.")

            experience = CandidateExperience(
                candidate_id=candidate.id,
                institution_name=item.institution_name,
                designation=item.designation,
                from_date=item.from_date,
                to_date=item.to_date,
                is_current=item.is_current,
                experience_type=item.experience_type.value,
            )
            db.add(experience)
            created.append(experience)

        await db.flush()
        await self._write_audit(
            db,
            "CandidateExperience",
            self._entity_id_from_uuid(candidate.id),
            "ADD_EXPERIENCE",
            current_user.id,
            new_value={"count": len(created)},
        )
        await db.commit()
        return created

    async def get_profile_by_candidate_id(self, db: AsyncSession, candidate_id: str) -> Candidate:
        stmt = (
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.qualifications),
                selectinload(Candidate.experiences),
            )
        )
        candidate = (await db.execute(stmt)).scalars().first()
        if not candidate:
            self._raise_error(404, "NOT_FOUND", "Candidate profile not found")
        return candidate
