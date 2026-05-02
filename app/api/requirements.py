import math
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func
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
    CourseUpdate, CourseResponse,
    IntakeCreate, IntakeResponse,
    CourseSetupRequest, CourseSetupResponse,
    GenerateRequirementRequest, RequirementResponse,
    AIValidationResponse
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

# Instantiate AI components
ai_engine = RequirementAIEngine()
ai_service = RequirementAIService(ai_engine)
vacancy_controller = VacancyController()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/requirements", tags=["Requirements (Step 1)"])

admin_only = RoleChecker([RoleEnum.ADMIN])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])

async def log_audit(db: AsyncSession, entity_name: str, entity_id: Any, action: str, user_id: int, new_val: dict = None):
    audit = AuditLog(entity_name=entity_name, entity_id=str(entity_id), action=action, user_id=user_id, new_value=new_val)
    db.add(audit)
    await db.flush()

@router.post("/institutions", response_model=InstitutionResponse, dependencies=[Depends(admin_only)])
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

@router.patch("/institutions/{institution_id}", response_model=InstitutionResponse, dependencies=[Depends(admin_only)])
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

@router.delete("/institutions/{institution_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(admin_only)])
async def delete_institution(
    institution_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Enterprise-grade deletion of an institution.
    
    - Requires ADMIN role.
    - Cascades deletion to Courses, Intakes, Norms, Requirements, Vacancies, and Advertisements.
    - Users associated with the institution are NOT deleted but unlinked.
    - Includes audit logging.
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
    
    # 3. Perform Deletion
    try:
        await db.delete(inst)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete institution {institution_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "code": "DELETION_FAILED",
                "message": "An error occurred while deleting the institution and its related data."
            }
        )
    
    return None

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

@router.patch("/courses/{course_id}", dependencies=[Depends(admin_only)])
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


@router.post("/norms/seed-dte-defaults", dependencies=[Depends(admin_only)])
async def seed_dte_defaults_endpoint(
    body: SeedDTEDefaultsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Idempotent: seed all 5 DTE course-wise norms for an institution."""
    result = await svc_seed_dte_defaults(
        institution_id=body.institution_id,
        academic_year=body.academic_year,
        faculty_student_ratio=body.faculty_student_ratio,
        created_by=current_user.id,
        db=db,
    )
    return {"status": "success", "data": result}


@router.post("/norms", dependencies=[Depends(admin_only)])
async def create_norm(
    norm_in: NormCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin creates a single institution-scoped norm."""
    result = await svc_create_norm(
        payload=norm_in,
        institution_id=current_user.institution_id,
        created_by=current_user.id,
        db=db,
    )
    return {"status": "success", "data": result}


@router.get("/norms") # Cannot use response_model directly due to validation format. Returning raw dict.
async def get_norms(
    academic_year: str,
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = None,
    norm_type: Optional[NormType] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List norms filtered by institution + academic year.
    PRINCIPAL: institution_id auto-set from token; cannot query other institutions.
    ADMIN: institution_id required as query param.
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
                    "message": "institution_id is required for ADMIN role.",
                },
            )
        resolved_institution_id = institution_id

    stmt = select(Norm).where(
        Norm.institution_id == resolved_institution_id,
        Norm.academic_year == academic_year,
    )
    if norm_type is not None:
        stmt = stmt.where(Norm.norm_type == norm_type.value)

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


@router.patch("/norms/{norm_id}", dependencies=[Depends(admin_only)])
async def update_norm(norm_id: int, norm_in: NormUpdate, db: AsyncSession = Depends(get_db)):
    """Update norm details."""
    result = await db.execute(select(Norm).filter(Norm.id == norm_id))
    norm = result.scalars().first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")

    update_data = norm_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(norm, field, value)

    await db.commit()
    await db.refresh(norm)
    return {"status": "success", "data": norm}

@router.post("/intake", response_model=IntakeResponse, dependencies=[Depends(admin_only)])
async def define_intake(intake_in: IntakeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Admin defines student intake for a specific Course (resolved by name and institution)."""
    # Look up Course by institution and name
    course_stmt = select(Course).filter(
        Course.institution_id == intake_in.institution_id,
        Course.name == intake_in.course_name
    )
    result = await db.execute(course_stmt)
    course_obj = result.scalars().first()
    
    if not course_obj:
        raise HTTPException(
            status_code=404, 
            detail=f"Course '{intake_in.course_name}' not found in institution {intake_in.institution_id}"
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
        "institution_id": intake_in.institution_id,
        "course_name": intake_in.course_name,
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
            "course_name": i.course.name,
            "academic_year": i.academic_year,
            "approved_seats": i.approved_seats,
            "actual_admitted": i.actual_admitted
        }
        for i in intakes
    ]


@router.post("/course-setup", response_model=CourseSetupResponse, dependencies=[Depends(admin_only)])
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
            "course_name": course_obj.name,
            "academic_year": i.academic_year,
            "approved_seats": i.approved_seats,
            "actual_admitted": i.actual_admitted
        }
        for i in intakes
    ]




@router.post("/generate", response_model=RequirementResponse, dependencies=[Depends(admin_only)])
async def generate_requirements(gen_req: GenerateRequirementRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Calculate required faculty using complex relational logic and JSONB formula."""
    result = await db.execute(
        select(IntakeDefinition)
        .filter(IntakeDefinition.id == gen_req.intake_id)
        .options(selectinload(IntakeDefinition.course))
    )
    intake = result.scalars().first()
    if not intake:
        raise HTTPException(status_code=404, detail="Intake Definition not found")

    # Resolve institution_id from Course → institution
    course = intake.course
    institution_id = course.institution_id

    # Derive course_category from request or Course metadata
    course_category: Optional[CourseCategory] = gen_req.course_category
    if course_category is None:
        legacy_cat = derive_course_category(course.name, course.level)
        if legacy_cat:
            # Map legacy string to CourseCategory enum where possible
            _legacy_map = {
                "Engineering Diploma": CourseCategory.ENGINEERING_DIPLOMA,
                "Engineering Degree": CourseCategory.ENGINEERING_DEGREE,

                "HMCT": CourseCategory.HMCT,
                "Applied Sciences": CourseCategory.APPLIED_SCIENCES,
            }
            course_category = _legacy_map.get(legacy_cat)

    # Resolve norm — raises HTTP 400 if not configured (AI call must NOT run)
    norm = await svc_resolve_norm(
        institution_id=institution_id,
        academic_year=intake.academic_year,
        course_category=course_category,
        db=db,
    )

    # Compute required faculty from resolved norm ratio
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

    await log_audit(db, "FacultyRequirement", req.id, "GENERATE", current_user.id, formula_json)
    await db.commit()

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
    return req_obj

@router.post("/validate", response_model=AIValidationResponse, dependencies=[Depends(admin_only)])
async def validate_requirements(gen_req: GenerateRequirementRequest, db: AsyncSession = Depends(get_db)):
    """Flags anomalies and returns AI-augmented analysis."""
    result = await db.execute(
        select(FacultyRequirement)
        .filter(FacultyRequirement.intake_id == gen_req.intake_id)
        .options(
            selectinload(FacultyRequirement.intake).selectinload(IntakeDefinition.course),
            selectinload(FacultyRequirement.anomalies)
        )
        .order_by(FacultyRequirement.id.desc())
    )
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Faculty Requirement not generated yet")
    
    # 1. Clear old anomalies (Enterprise: keeps table clean)
    await db.execute(delete(RequirementAnomaly).filter(RequirementAnomaly.requirement_id == req.id))
    
    # 2. Prepare payload for AI Engine
    ai_payload = {
        "intake_id": req.intake_id,
        "approved_seats": req.intake.approved_seats,
        "actual_admitted": req.intake.actual_admitted,
        "computed_required_count": req.computed_required_count,
        "norm_ratio": req.formula_breakdown.get("norm_ratio_applied", 0),
        "course_level": req.intake.course.level
    }
    
    # Optional: Fetch historical data (last year) when available.
    history = await _get_historical_data(db, req.intake.course_id, req.intake.academic_year)
    
    # 3. Centralized AI/Rule Analysis
    ai_result = await ai_service.validate_with_ai(ai_payload, history)
    
    # 4. Persist hardcoded anomalies detected by engine (for auditability)
    for anomaly_data in ai_result.get("anomalies", []):
        # Only persist rules that the engine identifies as "Rules" (internal)
        # For simplicity, we persist all high-severity ones
        if anomaly_data.get("severity") in ["HIGH", "CRITICAL"]:
            new_anom = RequirementAnomaly(
                requirement_id=req.id,
                severity=anomaly_data["severity"],
                description=anomaly_data["message"]
            )
            db.add(new_anom)
    
    await db.commit()
    
    # 5. Prepare Response
    return {
        "status": "success",
        "data": {
            "requirement": req,
            "ai_analysis": ai_result
        }
    }

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
