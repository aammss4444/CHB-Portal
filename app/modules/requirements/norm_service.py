import math
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.institution import Course
from app.models.norm import Norm
from app.modules.requirements.norm_constants import (
    CourseCategory,
    DTE_COURSE_NORM_DEFAULTS,
    NormType,
)
from app.schemas.norms import (
    NormCreate,
    NormResponse,
    SeedDTEDefaultsResponse,
)


async def _write_audit(
    db: AsyncSession,
    action: str,
    entity_id: int,
    performed_by: int,
    detail: dict,
) -> None:
    db.add(
        AuditLog(
            entity_name="Norm",
            entity_id=str(entity_id),
            action=action,
            user_id=performed_by,
            new_value=detail,
        )
    )
    await db.flush()


async def resolve_norm(
    institution_id: int,
    academic_year: str,
    course_id: Optional[int],
    course_category: Optional[CourseCategory],
    db: AsyncSession,
) -> Norm:
    """
    Resolve the applicable norm for a faculty requirement calculation.

    Priority:
      1. COURSE_WISE norm matching institution + year + course_id
      2. Backward-compat COURSE_WISE by course_category
      3. GENERAL norm matching institution + year
      4. HTTP 400 with code NORM_NOT_CONFIGURED
    """
    if course_id is not None:
        stmt = select(Norm).where(
            Norm.institution_id == institution_id,
            Norm.academic_year == academic_year,
            Norm.norm_type == NormType.COURSE_WISE.value,
            Norm.course_id == course_id,
        )
        result = await db.execute(stmt)
        norm = result.scalars().first()
        if norm:
            return norm

    if course_category is not None:
        stmt = select(Norm).where(
            Norm.institution_id == institution_id,
            Norm.academic_year == academic_year,
            Norm.norm_type == NormType.COURSE_WISE.value,
            Norm.course_category == course_category.value,
        )
        result = await db.execute(stmt)
        norm = result.scalars().first()
        if norm:
            return norm

    stmt = select(Norm).where(
        Norm.institution_id == institution_id,
        Norm.academic_year == academic_year,
        Norm.norm_type == NormType.GENERAL.value,
    )
    result = await db.execute(stmt)
    norm = result.scalars().first()
    if norm:
        return norm

    raise HTTPException(
        status_code=400,
        detail={
            "status": "error",
            "code": "NORM_NOT_CONFIGURED",
            "message": (
                "No norm configured for this institution and academic year. "
                "Admin must define norms before generating requirements."
            ),
        },
    )


async def create_norm(
    payload: NormCreate,
    institution_id: int,
    created_by: int,
    db: AsyncSession,
) -> NormResponse:
    """
    Create a single norm entry.

    Uniqueness:
      - COURSE_WISE: institution + year + norm_type + course_id
      - GENERAL: institution + year + norm_type (course_id must be null)
    """
    stmt = select(Norm).where(
        Norm.institution_id == institution_id,
        Norm.academic_year == payload.academic_year,
        Norm.norm_type == payload.norm_type.value,
    )
    if payload.norm_type == NormType.COURSE_WISE:
        course = (await db.execute(select(Course).where(Course.id == payload.course_id))).scalars().first()
        if not course:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "code": "COURSE_NOT_FOUND",
                    "message": "course_id does not exist.",
                },
            )
        if course.institution_id != institution_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "code": "COURSE_SCOPE_MISMATCH",
                    "message": "course_id does not belong to the current institution scope.",
                },
            )

    if payload.norm_type == NormType.COURSE_WISE:
        stmt = stmt.where(Norm.course_id == payload.course_id)
    else:
        stmt = stmt.where(Norm.course_id.is_(None))

    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "code": "NORM_ALREADY_EXISTS",
                "message": (
                    "A norm of this type already exists for this institution and academic year."
                ),
            },
        )

    norm = Norm(
        institution_id=institution_id,
        course_id=payload.course_id,
        academic_year=payload.academic_year,
        norm_type=payload.norm_type.value,
        course_category=payload.course_category.value if payload.course_category else None,
        min_qualification=payload.min_qualification,
        grade_requirement=payload.grade_requirement,
        faculty_student_ratio=payload.faculty_student_ratio,
        max_age=payload.max_age,
        workload_hours_per_week=payload.workload_hours_per_week,
    )
    db.add(norm)
    await db.flush()

    await _write_audit(
        db,
        action="NORM_CREATED",
        entity_id=norm.id,
        performed_by=created_by,
        detail={
            "norm_type": norm.norm_type,
            "course_id": norm.course_id,
            "course_category": norm.course_category,
            "academic_year": norm.academic_year,
            "faculty_student_ratio": norm.faculty_student_ratio,
        },
    )
    await db.commit()
    await db.refresh(norm)
    return NormResponse.model_validate(norm)


async def seed_dte_defaults(
    institution_id: int,
    academic_year: str,
    faculty_student_ratio: int,
    created_by: int,
    db: AsyncSession,
) -> SeedDTEDefaultsResponse:
    """
    Legacy category seeding for backward compatibility.
    """
    seeded = 0
    skipped = 0
    detail: list[str] = []

    for category, defaults in DTE_COURSE_NORM_DEFAULTS.items():
        stmt = select(Norm).where(
            Norm.institution_id == institution_id,
            Norm.academic_year == academic_year,
            Norm.norm_type == NormType.COURSE_WISE.value,
            Norm.course_category == category.value,
        )
        existing = (await db.execute(stmt)).scalars().first()

        if existing:
            skipped += 1
            detail.append(f"{category.value}: skipped (already exists)")
            continue

        norm = Norm(
            institution_id=institution_id,
            academic_year=academic_year,
            norm_type=NormType.COURSE_WISE.value,
            course_category=category.value,
            min_qualification=defaults["min_qualification"],
            grade_requirement=defaults["grade_requirement"],
            faculty_student_ratio=faculty_student_ratio,
            max_age=38,
            workload_hours_per_week=18,
        )
        db.add(norm)
        await db.flush()

        await _write_audit(
            db,
            action="NORM_CREATED",
            entity_id=norm.id,
            performed_by=created_by,
            detail={
                "norm_type": NormType.COURSE_WISE.value,
                "course_category": category.value,
                "academic_year": academic_year,
                "faculty_student_ratio": faculty_student_ratio,
                "source": "seed_dte_defaults",
            },
        )
        seeded += 1
        detail.append(f"{category.value}: seeded")

    await db.commit()
    return SeedDTEDefaultsResponse(seeded=seeded, skipped=skipped, detail=detail)
