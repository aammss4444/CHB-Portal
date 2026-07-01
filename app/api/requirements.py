import math
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func, update
from sqlalchemy.orm import selectinload
from typing import List, Optional, Any, Dict

from app.db.session import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.user import User, RoleEnum
from app.models.institution import Institution, Course
from app.models.intake import IntakeDefinition
from app.models.norm import Norm
from app.schemas.pagination import PaginatedResponse
from app.dependencies.pagination import PaginationParams, paginate
from app.models.faculty_req import FacultyRequirement, RequirementAnomaly
from app.models.audit import AuditLog
from app.schemas.requirement import (
    InstitutionCreate, InstitutionResponse, InstitutionUpdate,
    CourseCreate, CourseUpdate, CourseResponse,
    IntakeCreate, IntakeResponse, IntakeUpdate,
    CourseSetupRequest, CourseSetupResponse,
    GenerateRequirementRequest, RequirementResponse,
    AIQueryRequest, AIQueryResponse
)
from app.schemas.norms import (
    NormCreate,
    NormResponse,
    NormUpdate,
    NormUsedResponse,
    SeedDTEDefaultsRequest,
    SeedDTEDefaultsResponse,
    NORM_TYPES,
    COURSE_CATEGORIES,
    COURSE_WISE_DTE_DEFAULTS,
)
from app.modules.requirements.norm_constants import (
    CourseCategory,
    DTE_COURSE_NORM_DEFAULTS,
    NormType,
)
from app.dependencies.institution_scope import verify_institution_access
from app.modules.requirements.norm_service import (
    create_norm as svc_create_norm,
    resolve_norm as svc_resolve_norm,
    seed_dte_defaults as svc_seed_dte_defaults,
)
from app.modules.requirements.ai_engine import RequirementAIEngine
from app.modules.requirements.ai_service import RequirementAIService
from app.modules.requirements.norms_service import derive_course_category
from app.core.config import settings
from app.services.llm_service import llm_service
from app.modules.vacancy.controller import VacancyController
from app.models.vacancy_assessment import VacancyAssessment

# Instantiate AI components
ai_engine = RequirementAIEngine()
ai_service = RequirementAIService(ai_engine)
vacancy_controller = VacancyController()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/requirements", tags=["Requirements (Step 1)"])

admin_only = RoleChecker([RoleEnum.ADMIN])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])
ro_only = RoleChecker([RoleEnum.RO])
admin_or_ro = RoleChecker([RoleEnum.ADMIN, RoleEnum.RO])
ro_or_principal = RoleChecker([RoleEnum.RO, RoleEnum.PRINCIPAL])

async def log_audit(db: AsyncSession, entity_name: str, entity_id: Any, action: str, user_id: int, new_val: dict = None):
    audit = AuditLog(entity_name=entity_name, entity_id=str(entity_id), action=action, user_id=user_id, new_value=new_val)
    db.add(audit)
    await db.flush()

@router.post("/institutions", response_model=InstitutionResponse, dependencies=[Depends(ro_only)])
async def create_institution(inst_in: InstitutionCreate, db: AsyncSession = Depends(get_db)):
    """Seed data: Create Institution and its Courses."""
    # Check if code already exists
    existing_stmt = select(Institution).filter(Institution.code == inst_in.code)
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        raise HTTPException(status_code=400, detail=f"Institution with code {inst_in.code} already exists")

    inst = Institution(name=inst_in.name, code=inst_in.code, district=inst_in.district, type=inst_in.type)
    db.add(inst)
    await db.flush()

    for course_in in inst_in.courses:
        course = Course(institution_id=inst.id, name=course_in.name, level=course_in.level)
        db.add(course)
    await db.commit()
    
    # Re-fetch with courses loaded to avoid MissingGreenlet error during serialization
    result = await db.execute(
        select(Institution)
        .filter(Institution.id == inst.id)
        .options(selectinload(Institution.courses))
    )
    return result.scalars().first()

@router.get("/institutions", response_model=PaginatedResponse[InstitutionResponse])
async def get_institutions(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """List all institutions with their courses."""
    query = select(Institution).options(selectinload(Institution.courses))
    return await paginate(db, query, pagination)

@router.patch("/institutions/{institution_id}", response_model=InstitutionResponse, dependencies=[Depends(admin_or_ro)])
async def update_institution(institution_id: int, inst_in: InstitutionUpdate, db: AsyncSession = Depends(get_db)):
    """Update institution details."""
    result = await db.execute(select(Institution).filter(Institution.id == institution_id))
    inst = result.scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    
    update_data = inst_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inst, field, value)
    
    await db.commit()
    await db.refresh(inst)
    
    # Re-fetch with courses
    result = await db.execute(
        select(Institution)
        .filter(Institution.id == inst.id)
        .options(selectinload(Institution.courses))
    )
    return result.scalars().first()

@router.delete("/institutions/{institution_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(admin_or_ro)])
async def delete_institution(
    institution_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Delete an institution and ALL related data across the entire schema.
    Uses topologically-ordered SQL deletes to respect FK constraints.
    """
    # 1. Verify existence
    result = await db.execute(select(Institution).filter(Institution.id == institution_id))
    inst = result.scalars().first()
    if not inst:
        raise HTTPException(
            status_code=404, 
            detail={
                "status": "error",
                "code": "INSTITUTION_NOT_FOUND",
                "message": f"Institution with ID {institution_id} not found."
            }
        )
    
    # 2. Log Audit Trail before deletion
    await log_audit(
        db, 
        "Institution", 
        inst.id, 
        "DELETE", 
        current_user.id, 
        {
            "name": inst.name, 
            "code": inst.code,
            "district": inst.district,
            "type": inst.type
        }
    )
    
    # 3. Perform Deletion - disable FK checks, delete everything, re-enable
    try:
        # Disable FK constraint triggers for this transaction
        await db.execute(text("SET session_replication_role = 'replica'"))

        # Delete from ALL tables that reference this institution
        all_tables = [
            "lecture_log_audit", "bill_audit", "payment_transaction", "bill_line_item",
            "bill_approval", "appointment_audit", "appointment_acceptances",
            "advertisement_audit", "published_advertisements", "shortlisted_candidates",
            "selection_ai_snapshots", "scoring_weight_configs", "selection_rounds",
            "application_documents", "document_validation_log",
            "vacancy_anomalies", "candidate_scores", "interview_marks",
            "faculty_credentials", "existing_faculty", "selection_results",
            "appointment_letters", "applications", "advertisements",
            "vacancy_assessments", "chb_bill", "timetable_slots",
            "daily_attendance_summary", "attendance_anomalies", "lecture_logs",
            "rate_master", "academic_calendar", "norms", "intake_definitions",
            "requirement_anomalies", "faculty_requirements", "faculty_qualifications",
            "courses",
        ]

        for table in all_tables:
            try:
                async with db.begin_nested():
                    await db.execute(
                        text(f"DELETE FROM {table} WHERE institution_id = :id"),
                        {"id": institution_id}
                    )
            except Exception:
                pass  # Table might not have institution_id column - savepoint rolled back

        # Also delete nested rows that reference via subquery
        nested_deletes = [
            "DELETE FROM lecture_log_audit WHERE lecture_log_id IN (SELECT id FROM lecture_logs WHERE institution_id = :id)",
            "DELETE FROM bill_audit WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
            "DELETE FROM payment_transaction WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
            "DELETE FROM bill_line_item WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
            "DELETE FROM bill_approval WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
            "DELETE FROM appointment_audit WHERE appointment_letter_id IN (SELECT id FROM appointment_letters WHERE institution_id = :id)",
            "DELETE FROM appointment_acceptances WHERE appointment_letter_id IN (SELECT id FROM appointment_letters WHERE institution_id = :id)",
            "DELETE FROM advertisement_audit WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
            "DELETE FROM published_advertisements WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
            "DELETE FROM shortlisted_candidates WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
            "DELETE FROM selection_ai_snapshots WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
            "DELETE FROM scoring_weight_configs WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
            "DELETE FROM application_documents WHERE application_id IN (SELECT id FROM applications WHERE institution_id = :id)",
            "DELETE FROM document_validation_log WHERE application_id IN (SELECT id FROM applications WHERE institution_id = :id)",
        ]
        for query in nested_deletes:
            try:
                async with db.begin_nested():
                    await db.execute(text(query), {"id": institution_id})
            except Exception:
                pass

        # Unlink users
        async with db.begin_nested():
            await db.execute(
                text("UPDATE users SET institution_id = NULL WHERE institution_id = :id"),
                {"id": institution_id}
            )

        # Delete the institution
        async with db.begin_nested():
            await db.execute(
                text("DELETE FROM institutions WHERE id = :id"),
                {"id": institution_id}
            )

        # Re-enable FK constraint triggers
        await db.execute(text("SET session_replication_role = 'origin'"))

        await db.commit()
    except Exception as e:
        await db.rollback()
        # Ensure we re-enable triggers even on failure
        try:
            await db.execute(text("SET session_replication_role = 'origin'"))
        except Exception:
            pass
        logger.error(f"Failed to delete institution {institution_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "code": "DELETION_FAILED",
                "message": f"Delete failed: {str(e)}"
            }
        )
    
    return {"status": "success", "message": f"Institution {institution_id} and all related data have been deleted."}
    
@router.post("/institutions/{institution_id}/courses", response_model=CourseResponse, dependencies=[Depends(admin_or_ro)])
async def add_course_to_institution(
    institution_id: int, 
    course_in: CourseCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new course to an existing institution."""
    # 1. Verify institution existence
    result = await db.execute(select(Institution).filter(Institution.id == institution_id))
    inst = result.scalars().first()
    if not inst:
        raise HTTPException(
            status_code=404, 
            detail={
                "status": "error",
                "code": "INSTITUTION_NOT_FOUND",
                "message": f"Institution with ID {institution_id} not found."
            }
        )
    
    # 2. Check for duplicates
    existing_stmt = select(Course).filter(
        Course.institution_id == institution_id,
        Course.name == course_in.name,
        Course.level == course_in.level
    )
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        raise HTTPException(
            status_code=400, 
            detail={
                "status": "error",
                "code": "DUPLICATE_COURSE",
                "message": f"Course '{course_in.name}' ({course_in.level}) already exists in this institution."
            }
        )
    
    # 3. Create Course
    course = Course(institution_id=institution_id, name=course_in.name, level=course_in.level)
    db.add(course)
    await db.flush()
    
    # 4. Audit Log
    await log_audit(
        db, 
        "Course", 
        course.id, 
        "CREATE", 
        current_user.id, 
        {"name": course.name, "level": course.level, "institution_id": institution_id}
    )
    
    await db.commit()
    await db.refresh(course)
    return course

@router.get("/courses", response_model=PaginatedResponse[CourseResponse])
async def get_courses(
    institution_id: Optional[int] = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """List all courses, optionally filtered by institution."""
    query = select(Course)
    if institution_id:
        query = query.where(Course.institution_id == institution_id)
    return await paginate(db, query, pagination)

@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, db: AsyncSession = Depends(get_db)):
    """Get specific course details."""
    result = await db.execute(select(Course).filter(Course.id == course_id))
    course = result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@router.patch("/courses/{course_id}", dependencies=[Depends(admin_or_ro)])
async def update_course(course_id: int, course_in: CourseUpdate, db: AsyncSession = Depends(get_db)):
    """Update Course details."""
    result = await db.execute(select(Course).filter(Course.id == course_id))
    course_obj = result.scalars().first()
    if not course_obj:
        raise HTTPException(status_code=404, detail="Course not found")
    
    update_data = course_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course_obj, field, value)
    
    await db.commit()
    return {"status": "success", "message": "Course updated"}


@router.delete("/courses/{course_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(admin_or_ro)])
async def delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete course and its dependent entities via DB cascades."""
    result = await db.execute(select(Course).filter(Course.id == course_id))
    course_obj = result.scalars().first()
    if not course_obj:
        raise HTTPException(status_code=404, detail="Course not found")

    await log_audit(
        db,
        "Course",
        course_obj.id,
        "DELETE",
        current_user.id,
        {
            "institution_id": course_obj.institution_id,
            "name": course_obj.name,
            "level": course_obj.level,
        },
    )
    await db.delete(course_obj)
    await db.commit()
    return {"status": "success", "message": f"Course {course_id} has been deleted."}


@router.get("/norms/types")
async def get_norm_types():
    return {"types": [t.value for t in NormType]}


@router.get("/norms/courses")
async def get_course_categories():
    return [
        {
            "course_category": cat.value,
            "min_qualification": defaults["min_qualification"],
            "grade_requirement": defaults["grade_requirement"],
        }
        for cat, defaults in DTE_COURSE_NORM_DEFAULTS.items()
    ]


@router.post("/norms/seed-dte-defaults", dependencies=[Depends(ro_or_principal)])
async def seed_dte_defaults_endpoint(
    body: SeedDTEDefaultsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Idempotent: seed all 5 DTE course-wise norms for an institution."""
    if current_user.role == RoleEnum.PRINCIPAL:
        resolved_institution_id = current_user.institution_id
    else:
        resolved_institution_id = body.institution_id

    await verify_institution_access(resolved_institution_id, current_user)

    result = await svc_seed_dte_defaults(
        institution_id=resolved_institution_id,
        academic_year=body.academic_year,
        faculty_student_ratio=body.faculty_student_ratio,
        created_by=current_user.id,
        db=db,
    )
    return {"status": "success", "data": result}


@router.post("/norms", dependencies=[Depends(ro_or_principal)])
async def create_norm(
    norm_in: NormCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RO creates a single institution-scoped norm."""
    if current_user.role == RoleEnum.PRINCIPAL:
        resolved_institution_id = current_user.institution_id
    else:
        if norm_in.institution_id is None:
            raise HTTPException(
                status_code=400,
                detail="institution_id is required for RO role."
            )
        resolved_institution_id = norm_in.institution_id

    result = await svc_create_norm(
        payload=norm_in,
        institution_id=resolved_institution_id,
        created_by=current_user.id,
        db=db,
    )
    return {"status": "success", "data": result}


@router.get("/norms") # Cannot use response_model directly due to validation format. Returning raw dict.
async def get_norms(
    academic_year: str,
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = None,
    course_id: Optional[int] = None,
    norm_type: Optional[NormType] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List norms filtered by institution + academic year.
    PRINCIPAL: institution_id auto-set from token; cannot query other institutions.
    RO: institution_id required as query param.
    """
    if current_user.role == RoleEnum.PRINCIPAL:
        resolved_institution_id = current_user.institution_id
    else:
        if institution_id is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "code": "UNAUTHORIZED_ACCESS",
                    "message": "institution_id is required for RO role.",
                },
            )
        resolved_institution_id = institution_id

    stmt = select(Norm).where(
        Norm.institution_id == resolved_institution_id,
        Norm.academic_year == academic_year,
    )
    if norm_type is not None:
        stmt = stmt.where(Norm.norm_type == norm_type.value)
    if course_id is not None:
        stmt = stmt.where(Norm.course_id == course_id)

    result = await db.execute(stmt.offset(pagination.skip).limit(pagination.limit))
    norms = result.scalars().all()
    
    # We still need count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    return {
        "status": "success",
        "data": [NormResponse.model_validate(n) for n in norms],
        "total": total,
        "page": pagination.page,
        "limit": pagination.limit,
        "total_pages": math.ceil(total / pagination.limit) if pagination.limit > 0 else 0
    }


@router.patch("/norms/{norm_id}", dependencies=[Depends(ro_or_principal)])
async def update_norm(norm_id: int, norm_in: NormUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update norm details."""
    result = await db.execute(select(Norm).filter(Norm.id == norm_id))
    norm = result.scalars().first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")
    
    await verify_institution_access(norm.institution_id, current_user)

    update_data = norm_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(norm, field, value)

    await db.commit()
    await db.refresh(norm)
    return {"status": "success", "data": norm}


@router.delete("/norms/{norm_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(ro_or_principal)])
async def delete_norm(
    norm_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a norm configuration."""
    result = await db.execute(select(Norm).filter(Norm.id == norm_id))
    norm = result.scalars().first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")

    await verify_institution_access(norm.institution_id, current_user)

    await log_audit(
        db,
        "Norm",
        norm.id,
        "DELETE",
        current_user.id,
        {
            "institution_id": norm.institution_id,
            "course_id": norm.course_id,
            "academic_year": norm.academic_year,
            "norm_type": norm.norm_type,
        },
    )
    await db.delete(norm)
    await db.commit()
    return {"status": "success", "message": f"Norm {norm_id} has been deleted."}

@router.post("/intake", response_model=IntakeResponse, dependencies=[Depends(ro_or_principal)])
async def define_intake(intake_in: IntakeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Define student intake for a specific Course."""
    # Resolve institution_id
    if current_user.role == RoleEnum.PRINCIPAL:
        resolved_institution_id = current_user.institution_id
    else:
        if intake_in.institution_id is None:
            raise HTTPException(status_code=400, detail="institution_id is required for RO role.")
        resolved_institution_id = intake_in.institution_id

    await verify_institution_access(resolved_institution_id, current_user)

    # Look up Course
    course_stmt = select(Course).filter(
        Course.institution_id == resolved_institution_id,
        Course.id == intake_in.course_id
    )
    result = await db.execute(course_stmt)
    course_obj = result.scalars().first()
    
    if not course_obj:
        raise HTTPException(
            status_code=404, 
            detail=f"Course ID {intake_in.course_id} not found in institution {intake_in.institution_id}"
        )

    intake = IntakeDefinition(
        course_id=course_obj.id, 
        academic_year=intake_in.academic_year, 
        approved_seats=intake_in.approved_seats, 
        actual_admitted=intake_in.actual_admitted
    )
    db.add(intake)
    await db.flush() # Flush to get ID
    
    await log_audit(db, "IntakeDefinition", intake.id, "CREATE", current_user.id, {"approved": intake.approved_seats})
    await db.commit()
    await db.refresh(intake)
    
    return {
        "id": intake.id,
        "institution_id": resolved_institution_id,
        "course_id": intake.course_id,
        "course_name": course_obj.name,
        "academic_year": intake.academic_year,
        "approved_seats": intake.approved_seats,
        "actual_admitted": intake.actual_admitted
    }


@router.get("/intake", response_model=List[IntakeResponse])
async def get_intakes(
    institution_id: Optional[int] = None,
    academic_year: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List intakes, optionally filtered by institution and academic year.
    Includes course name by joining with the Course table.
    """
    stmt = select(IntakeDefinition).options(selectinload(IntakeDefinition.course))
    
    if institution_id:
        stmt = stmt.join(Course).filter(Course.institution_id == institution_id)
    
    if academic_year:
        stmt = stmt.filter(IntakeDefinition.academic_year == academic_year)
        
    result = await db.execute(stmt)
    intakes = result.scalars().all()
    
    return [
        {
            "id": i.id,
            "institution_id": i.course.institution_id,
            "course_id": i.course_id,
            "course_name": i.course.name,
            "academic_year": i.academic_year,
            "approved_seats": i.approved_seats,
            "actual_admitted": i.actual_admitted
        }
        for i in intakes
    ]


@router.patch("/intake/{intake_id}", response_model=IntakeResponse, dependencies=[Depends(ro_or_principal)])
async def update_intake(
    intake_id: int,
    intake_in: IntakeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update intake seats/admissions for an intake record."""
    result = await db.execute(
        select(IntakeDefinition)
        .filter(IntakeDefinition.id == intake_id)
        .options(selectinload(IntakeDefinition.course))
    )
    intake = result.scalars().first()
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    
    await verify_institution_access(intake.course.institution_id, current_user)

    update_data = intake_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    for field, value in update_data.items():
        setattr(intake, field, value)

    await log_audit(db, "IntakeDefinition", intake.id, "UPDATE", current_user.id, update_data)
    await db.commit()
    await db.refresh(intake)

    return {
        "id": intake.id,
        "institution_id": intake.course.institution_id,
        "course_id": intake.course_id,
        "course_name": intake.course.name,
        "academic_year": intake.academic_year,
        "approved_seats": intake.approved_seats,
        "actual_admitted": intake.actual_admitted,
    }


@router.post("/course-setup", response_model=CourseSetupResponse, dependencies=[Depends(ro_only)])
async def course_setup(
    req: CourseSetupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unified API: Define both Intake and Norm for a specific course in one call.

    - Resolves the course by institution_id + course_name.
    - Creates or updates the IntakeDefinition for that course + academic_year.
    - Creates or updates the Norm for that course + academic_year.
    - Auto-derives course_category from course metadata if not provided.
    - Returns the complete setup result.
    """
    # 1. Resolve Course
    course_stmt = select(Course).filter(
        Course.institution_id == req.institution_id,
        Course.name == req.course_name
    )
    result = await db.execute(course_stmt)
    course_obj = result.scalars().first()
    if not course_obj:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "COURSE_NOT_FOUND",
                "message": f"Course '{req.course_name}' not found in institution {req.institution_id}."
            }
        )

    # 2. Create or Update IntakeDefinition
    intake_stmt = select(IntakeDefinition).filter(
        IntakeDefinition.course_id == course_obj.id,
        IntakeDefinition.academic_year == req.academic_year
    )
    intake_res = await db.execute(intake_stmt)
    intake = intake_res.scalars().first()

    if intake:
        # Update existing
        intake.approved_seats = req.approved_seats
        intake.actual_admitted = req.actual_admitted
        await log_audit(db, "IntakeDefinition", intake.id, "UPDATE", current_user.id, {
            "approved_seats": req.approved_seats, "actual_admitted": req.actual_admitted
        })
    else:
        # Create new
        intake = IntakeDefinition(
            course_id=course_obj.id,
            academic_year=req.academic_year,
            approved_seats=req.approved_seats,
            actual_admitted=req.actual_admitted
        )
        db.add(intake)
        await db.flush()
        await log_audit(db, "IntakeDefinition", intake.id, "CREATE", current_user.id, {
            "approved_seats": req.approved_seats, "actual_admitted": req.actual_admitted
        })

    # 3. Derive course_category if not provided
    course_category = req.course_category
    if not course_category:
        derived = derive_course_category(course_obj.name, course_obj.level)
        if derived:
            course_category = derived

    # 4. Create or Update Norm (course-specific)
    norm_stmt = select(Norm).filter(
        Norm.institution_id == req.institution_id,
        Norm.course_id == course_obj.id,
        Norm.academic_year == req.academic_year
    )
    norm_res = await db.execute(norm_stmt)
    norm = norm_res.scalars().first()

    if norm:
        # Update existing
        norm.faculty_student_ratio = req.faculty_student_ratio
        norm.min_qualification = req.min_qualification
        norm.grade_requirement = req.grade_requirement
        norm.norm_type = req.norm_type
        norm.course_category = course_category
        norm.max_age = req.max_age
        norm.workload_hours_per_week = req.workload_hours_per_week
        await log_audit(db, "Norm", norm.id, "UPDATE", current_user.id, {
            "faculty_student_ratio": req.faculty_student_ratio, "course_category": course_category
        })
    else:
        # Create new
        norm = Norm(
            institution_id=req.institution_id,
            course_id=course_obj.id,
            academic_year=req.academic_year,
            norm_type=req.norm_type,
            course_category=course_category,
            faculty_student_ratio=req.faculty_student_ratio,
            min_qualification=req.min_qualification,
            grade_requirement=req.grade_requirement,
            max_age=req.max_age,
            workload_hours_per_week=req.workload_hours_per_week,
        )
        db.add(norm)
        await db.flush()
        await log_audit(db, "Norm", norm.id, "CREATE", current_user.id, {
            "faculty_student_ratio": req.faculty_student_ratio, "course_category": course_category
        })

    await db.commit()
    await db.refresh(intake)
    await db.refresh(norm)

    return CourseSetupResponse(
        status="success",
        institution_id=req.institution_id,
        course_name=req.course_name,
        academic_year=req.academic_year,
        intake={
            "id": intake.id,
            "course_id": course_obj.id,
            "course_name": req.course_name,
            "academic_year": intake.academic_year,
            "approved_seats": intake.approved_seats,
            "actual_admitted": intake.actual_admitted,
        },
        norm={
            "id": norm.id,
            "institution_id": req.institution_id,
            "course_id": course_obj.id,
            "norm_type": norm.norm_type,
            "course_category": norm.course_category,
            "faculty_student_ratio": norm.faculty_student_ratio,
            "min_qualification": norm.min_qualification,
            "grade_requirement": norm.grade_requirement,
            "max_age": norm.max_age,
            "workload_hours_per_week": norm.workload_hours_per_week,
        },
    )



@router.get("/course-setup/{course_id}", response_model=CourseSetupResponse)
async def get_course_setup(
    course_id: int,
    academic_year: str = Query(..., description="Academic year (e.g., 2026-2027)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the Intake and Norm configuration for a specific course and academic year.
    """
    # 1. Resolve Course
    course_stmt = select(Course).filter(Course.id == course_id)
    result = await db.execute(course_stmt)
    course_obj = result.scalars().first()
    if not course_obj:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "COURSE_NOT_FOUND",
                "message": f"Course with ID {course_id} not found."
            }
        )

    # 2. Get IntakeDefinition
    intake_stmt = select(IntakeDefinition).filter(
        IntakeDefinition.course_id == course_id,
        IntakeDefinition.academic_year == academic_year
    )
    intake_res = await db.execute(intake_stmt)
    intake = intake_res.scalars().first()
    
    if not intake:
         raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "SETUP_NOT_FOUND",
                "message": f"No intake defined for course '{course_obj.name}' in academic year {academic_year}."
            }
        )

    # 3. Get Norm
    norm_stmt = select(Norm).filter(
        Norm.course_id == course_id,
        Norm.academic_year == academic_year
    )
    norm_res = await db.execute(norm_stmt)
    norm = norm_res.scalars().first()
    
    if not norm:
         raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "SETUP_NOT_FOUND",
                "message": f"No norm defined for course '{course_obj.name}' in academic year {academic_year}."
            }
        )

    return CourseSetupResponse(
        status="success",
        institution_id=course_obj.institution_id,
        course_name=course_obj.name,
        academic_year=academic_year,
        intake={
            "id": intake.id,
            "course_id": course_id,
            "course_name": course_obj.name,
            "academic_year": intake.academic_year,
            "approved_seats": intake.approved_seats,
            "actual_admitted": intake.actual_admitted,
        },
        norm={
            "id": norm.id,
            "institution_id": norm.institution_id,
            "course_id": course_id,
            "norm_type": norm.norm_type,
            "course_category": norm.course_category,
            "faculty_student_ratio": norm.faculty_student_ratio,
            "min_qualification": norm.min_qualification,
            "grade_requirement": norm.grade_requirement,
            "max_age": norm.max_age,
            "workload_hours_per_week": norm.workload_hours_per_week,
        },
    )


@router.get("/courses/{course_id}/intake", response_model=List[IntakeResponse])
async def get_course_intakes(course_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all intake counts (approved vs admitted) for a specific course across all years.
    """
    # 1. Resolve Course to ensure it exists
    course_stmt = select(Course).filter(Course.id == course_id)
    course_obj = (await db.execute(course_stmt)).scalars().first()
    if not course_obj:
        raise HTTPException(status_code=404, detail=f"Course ID {course_id} not found")

    # 2. Get all intake definitions
    stmt = select(IntakeDefinition).filter(IntakeDefinition.course_id == course_id).order_by(IntakeDefinition.academic_year.desc())
    result = await db.execute(stmt)
    intakes = result.scalars().all()

    # Format response to match IntakeResponse schema (which includes course_name)
    return [
        {
            "id": i.id,
            "institution_id": course_obj.institution_id,
            "course_id": i.course_id,
            "course_name": course_obj.name,
            "academic_year": i.academic_year,
            "approved_seats": i.approved_seats,
            "actual_admitted": i.actual_admitted
        }
        for i in intakes
    ]




@router.post("/generate", response_model=List[RequirementResponse], dependencies=[Depends(admin_or_principal)])
async def generate_requirements(gen_req: GenerateRequirementRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Calculate required faculty for one or multiple courses."""
    await verify_institution_access(gen_req.institution_id, current_user)

    # Base query for intakes
    stmt = select(IntakeDefinition).options(selectinload(IntakeDefinition.course)).filter(
        IntakeDefinition.academic_year == gen_req.academic_year
    ).join(Course).filter(
        Course.institution_id == gen_req.institution_id
    )

    if gen_req.course_id:
        stmt = stmt.filter(IntakeDefinition.course_id == gen_req.course_id)

    result = await db.execute(stmt)
    intakes = result.scalars().all()

    if not intakes:
        raise HTTPException(status_code=404, detail="No Intake Definitions found for the given criteria")

    responses = []

    for intake in intakes:
        course = intake.course
        
        # Derive course_category from request or Course metadata
        course_category: Optional[CourseCategory] = None
        if gen_req.course_category:
            course_category = CourseCategory(gen_req.course_category)
        else:
            legacy_cat = derive_course_category(course.name, course.level)
            if legacy_cat:
                _legacy_map = {
                    "Engineering & Technology (Diploma)": CourseCategory.ENGINEERING_DIPLOMA,
                    "Engineering (Degree - B.E./B.Tech)": CourseCategory.ENGINEERING_DEGREE,
                    "HMCT (Hotel Management)": CourseCategory.HMCT,
                    "Non-Engineering (Applied Sciences)": CourseCategory.APPLIED_SCIENCES,
                }
                course_category = _legacy_map.get(legacy_cat)

        try:
            # Resolve norm
            norm = await svc_resolve_norm(
                institution_id=gen_req.institution_id,
                academic_year=intake.academic_year,
                course_id=course.id,
                course_category=course_category,
                db=db,
            )

            # Compute required faculty
            calc_base = max(intake.approved_seats, intake.actual_admitted)
            required = math.ceil(calc_base / norm.faculty_student_ratio)

            formula_json = {
                "base_used": calc_base,
                "norm_ratio_applied": norm.faculty_student_ratio,
                "calculation": f"ceil({calc_base} / {norm.faculty_student_ratio})",
                "course_level": course.level,
                "norm_type": norm.norm_type,
                "course_category": norm.course_category or (course_category.value if course_category else None),
                "grade_requirement": norm.grade_requirement,
            }

            req = FacultyRequirement(intake_id=intake.id, computed_required_count=required, formula_breakdown=formula_json)
            db.add(req)
            await db.commit()

            # Step 1 changed: unlock Step 2 so Principal can reassess and reconfirm.
            await db.execute(
                update(VacancyAssessment)
                .where(
                    VacancyAssessment.institution_id == gen_req.institution_id,
                    VacancyAssessment.course_id == intake.course_id,
                    VacancyAssessment.academic_year == gen_req.academic_year,
                )
                .values(
                    status="DRAFT",
                    confirmed_vacancy=None,
                    confirmed_by=None,
                    confirmed_at=None,
                    requirement_id=req.id,
                )
            )
            await db.commit()

            await log_audit(db, "FacultyRequirement", req.id, "GENERATE", current_user.id, formula_json)
            
            # Re-fetch with anomalies loaded
            req_res = await db.execute(
                select(FacultyRequirement)
                .filter(FacultyRequirement.id == req.id)
                .options(selectinload(FacultyRequirement.anomalies))
            )
            req_obj = req_res.scalars().first()
            setattr(req_obj, "required_faculty", req_obj.computed_required_count)
            setattr(
                req_obj,
                "norm_used",
                {
                    "type": norm.norm_type or NormType.GENERAL.value,
                    "course_category": norm.course_category or (course_category.value if course_category else None),
                    "min_qualification": norm.min_qualification or "",
                    "grade_requirement": norm.grade_requirement or "",
                    "faculty_student_ratio": int(norm.faculty_student_ratio),
                },
            )
            responses.append(req_obj)
        except HTTPException as e:
            # If norm is missing for a specific course in bulk, skip and continue
            if gen_req.course_id:
                raise e # Throw if it was specifically requested
            continue

    if not responses and not gen_req.course_id:
        raise HTTPException(status_code=400, detail="Could not generate requirements. Norms might be missing for all courses.")

    return responses


@router.get("/ai-query", dependencies=[Depends(admin_only)])
async def ai_query_database(
    query: str, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Experimental: Automatic natural language query for Step 1 data.
    Uses LLM to generate SQL based on schema.
    """
    if not llm_service.enabled:
        raise HTTPException(status_code=400, detail="LLM service is disabled")

    # Schema context for the LLM
    schema_context = """
    Tables:
    - institutions: id, name, code, district, type
    - courses: id, institution_id, name, level
    - intake_definitions: id, course_id, academic_year, approved_seats, actual_admitted
    - faculty_requirements: id, intake_id, computed_required_count, created_at
    - norms: id, academic_year, norm_type, course_category, min_qualification, grade_requirement, faculty_student_ratio
    
    Relationships:
    - courses.institution_id -> institutions.id
    - intake_definitions.course_id -> courses.id
    - faculty_requirements.intake_id -> intake_definitions.id
    """

    prompt = f"""
    You are a SQL expert for a PostgreSQL database. 
    Based on the schema below, generate a read-only SELECT query to answer the user's question.
    
    Schema:
    {schema_context}
    
    User Question: {query}
    
    Return ONLY a JSON object with the key 'sql'. Do not explain.
    """
    
    ai_res = await llm_service.analyze_custom_json(prompt)
    if not ai_res or 'sql' not in ai_res:
        raise HTTPException(status_code=500, detail="AI failed to generate query")
    
    sql_query = ai_res['sql']
    
    # Basic safety check
    forbidden = ["insert", "update", "delete", "drop", "truncate", "alter"]
    if any(f in sql_query.lower() for f in forbidden):
         raise HTTPException(status_code=403, detail="Unauthorized query type generated by AI")

    try:
        result = await db.execute(text(sql_query))
        # Convert result to list of dicts
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in result.fetchall()]
        
        return {
            "query": query,
            "results": data,
            "count": len(data),
            # Debug info only if settings allow (Enterprise security)
            "debug": {"sql": sql_query} if settings.DEBUG else None
        }
    except Exception as e:
        logger.error(f"AI SQL execution failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to execute generated query: {str(e)}")

async def _get_historical_data(db: AsyncSession, course_id: int, current_year: str) -> Optional[dict]:
    """
    Attempts to fetch data for the same Course from the previous academic year.
    """
    # Logic to parse previous year (e.g., '2026-2027' -> '2025-2026')
    try:
        start_year = int(current_year.split("-")[0])
        prev_year = f"{start_year-1}-{start_year}"
        
        stmt = select(IntakeDefinition).filter(
            IntakeDefinition.course_id == course_id,
            IntakeDefinition.academic_year == prev_year
        ).options(selectinload(IntakeDefinition.faculty_requirements))
        
        res = await db.execute(stmt)
        prev_intake = res.scalars().first()
        
        if prev_intake and prev_intake.faculty_requirements:
            prev_req = max(prev_intake.faculty_requirements, key=lambda r: r.id)
            return {
                "previous_required_count": prev_req.computed_required_count,
                "previous_actual_admitted": prev_intake.actual_admitted
            }
    except (ValueError, IndexError) as exc:
        logger.warning("Invalid academic_year format '%s': %s", current_year, exc)
    except Exception as exc:
        logger.error("Failed to fetch historical data for Course=%s year=%s: %s", course_id, current_year, exc, exc_info=True)

    if settings.ALLOW_MOCK_HISTORY:
        return {
            "previous_required_count": 5,
            "previous_actual_admitted": 100,
        }
    return None


@router.get("/assessments", dependencies=[Depends(admin_only)])
async def legacy_assessments_alias(
    institution_id: str,
    course_id: str,
    academic_year: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Backward-compat alias for clients still calling /requirements/assessments."""
    def parse_int_like(value: str, field: str) -> int:
        if value.isdigit():
            return int(value)
        parts = value.split("-")
        if parts and parts[-1].isdigit():
            return int(parts[-1])
        raise HTTPException(status_code=422, detail=f"{field} must be an integer id")

    inst_id = parse_int_like(institution_id, "institution_id")
    br_id = parse_int_like(course_id, "course_id")
    return await vacancy_controller.get_assessment(db, current_user, inst_id, br_id, academic_year)
@router.post("/ai-query", dependencies=[Depends(admin_or_principal)])
async def faculty_requirement_calculator(
    request: AIQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Faculty Requirement Calculator (AI-Assisted).
    Calculates faculty requirements based on intake, course norms, and faculty-student ratios.
    Compares current requirements with historical utilization data.
    Flags abnormal variations for review.
    Returns a 'Suggested Requirement Summary' for Directorate approval.
    """
    inst_id = request.institution_id
    academic_year = request.context.get("academic_year", "2026-27") if request.context else "2026-27"
    course_id = request.context.get("course_id") if request.context else None

    # 1. Fetch Institution
    inst_stmt = select(Institution).filter(Institution.id == inst_id).options(selectinload(Institution.courses))
    inst = (await db.execute(inst_stmt)).scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    target_courses = inst.courses
    if course_id:
        target_courses = [c for c in inst.courses if c.id == int(course_id)]
        if not target_courses:
            raise HTTPException(status_code=404, detail="Course not found in this institution")

    course_summaries = []
    total_required = 0
    total_admitted = 0
    total_approved = 0
    all_anomalies = []
    all_insights = []
    overall_confidence = 1.0

    for course in target_courses:
        # 2. Fetch Intake
        intake_stmt = select(IntakeDefinition).filter(
            IntakeDefinition.course_id == course.id,
            IntakeDefinition.academic_year == academic_year
        )
        intake = (await db.execute(intake_stmt)).scalars().first()
        if not intake:
            continue

        # 3. Resolve Norm
        course_cat = None
        legacy_cat = derive_course_category(course.name, course.level)
        if legacy_cat:
            _legacy_map = {
                "Engineering Diploma": CourseCategory.ENGINEERING_DIPLOMA,
                "Engineering Degree": CourseCategory.ENGINEERING_DEGREE,
                "HMCT": CourseCategory.HMCT,
                "Applied Sciences": CourseCategory.APPLIED_SCIENCES,
            }
            course_cat = _legacy_map.get(legacy_cat)

        try:
            norm = await svc_resolve_norm(inst_id, academic_year, course.id, course_cat, db)
        except Exception:
            continue

        # 4. Calculate Requirement
        calc_base = max(intake.approved_seats, intake.actual_admitted)
        required = math.ceil(calc_base / norm.faculty_student_ratio)

        # 5. Fetch Historical Data
        history = await _get_historical_data(db, course.id, academic_year)

        # 6. Fetch Existing Faculty Count
        from app.models.existing_faculty import ExistingFaculty
        fac_stmt = select(func.count()).select_from(ExistingFaculty).filter(
            ExistingFaculty.institution_id == inst_id,
            ExistingFaculty.course_id == course.id,
            ExistingFaculty.academic_year == academic_year,
            ExistingFaculty.is_effective == True
        )
        existing_count = (await db.execute(fac_stmt)).scalar() or 0

        # 7. Run AI Engine for this course
        ai_data = {
            "intake_id": intake.id,
            "approved_seats": intake.approved_seats,
            "actual_admitted": intake.actual_admitted,
            "computed_required_count": required,
            "norm_ratio": norm.faculty_student_ratio,
            "branch_level": course.level,
        }
        ai_result = await ai_service.validate_with_ai(ai_data, history)

        # 8. Save to Database
        req_stmt = select(FacultyRequirement).where(FacultyRequirement.intake_id == intake.id)
        existing_req = (await db.execute(req_stmt)).scalars().first()
        
        formula = {
            "calc_base": calc_base,
            "norm_ratio": float(norm.faculty_student_ratio),
            "required": required
        }

        if existing_req:
            existing_req.computed_required_count = required
            existing_req.formula_breakdown = formula
            await db.execute(delete(RequirementAnomaly).where(RequirementAnomaly.requirement_id == existing_req.id))
            req_obj = existing_req
        else:
            req_obj = FacultyRequirement(
                intake_id=intake.id,
                computed_required_count=required,
                formula_breakdown=formula
            )
            db.add(req_obj)
            
        await db.flush()

        for anomaly_data in ai_result.get("anomalies", []):
            db.add(RequirementAnomaly(
                requirement_id=req_obj.id,
                severity=anomaly_data.get("severity", "MEDIUM"),
                description=anomaly_data.get("description", "AI detected anomaly")
            ))

        # 9. Build course summary
        vacancy_gap = max(0, required - existing_count)
        course_summary = {
            "course_id": course.id,
            "course_name": course.name,
            "level": course.level,
            "approved_seats": intake.approved_seats,
            "actual_admitted": intake.actual_admitted,
            "norm_ratio": int(norm.faculty_student_ratio),
            "computed_required": required,
            "existing_faculty": existing_count,
            "vacancy_gap": vacancy_gap,
            "historical": history,
            "ai_status": ai_result.get("status", "OK"),
            "anomaly_count": len(ai_result.get("anomalies", [])),
        }
        course_summaries.append(course_summary)

        total_required += required
        total_admitted += intake.actual_admitted
        total_approved += intake.approved_seats
        all_anomalies.extend(ai_result.get("anomalies", []))
        all_insights.extend(ai_result.get("insights", []))
        overall_confidence = min(overall_confidence, ai_result.get("confidence_score", 1.0))

    # 9. Build Final Summary
    summary_text = (
        f"Faculty Requirement Summary for {inst.name} ({academic_year}):\n"
        f"• Total Courses Analyzed: {len(course_summaries)}\n"
        f"• Total Students Admitted: {total_admitted} / {total_approved} approved\n"
        f"• Total Faculty Required (by norms): {total_required}\n"
        f"• Anomalies Detected: {len(all_anomalies)}\n"
    )
    if all_anomalies:
        summary_text += "\n⚠ Review required: The AI engine flagged variations in one or more courses."
    else:
        summary_text += "\n✓ All requirements are within normal parameters."
        
    await db.commit()

    return {
        "answer": summary_text,
        "data": {
            "institution": {"id": inst.id, "name": inst.name, "code": inst.code},
            "academic_year": academic_year,
            "total_required": total_required,
            "total_admitted": total_admitted,
            "total_approved": total_approved,
            "courses": course_summaries,
            "anomalies": all_anomalies,
            "insights": list(dict.fromkeys(all_insights)),  # deduplicate
        },
        "confidence_score": round(overall_confidence, 2),
    }
