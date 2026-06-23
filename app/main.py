# Heartbeat: 2026-05-04 18:05
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse
from datetime import datetime
from contextlib import asynccontextmanager
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.db.session import engine, Base
from app.api.auth import router as auth_router
from app.api.requirements import router as req_router
from app.modules.vacancy.router import router as vacancy_router
from app.modules.advertisement.router import router as ad_router
from app.modules.candidate.router import router as candidate_router
from app.modules.application.router import router as app_router
from app.modules.selection.router import router as selection_router
from app.modules.scoring_weights.router import router as weight_router
from app.modules.appointment.router import router as appointment_router
from app.modules.attendance.router import router as attendance_router
from app.modules.billing.router import router as billing_router
from app.modules.payments.router import router as payments_router
from app.modules.audit.router import router as audit_router
from app.modules.principal.router import router as principal_router
from app.modules.helpdesk.router import router as helpdesk_router
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (For dev/Step 1. In prod use Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Backward-compatible hotfix for environments where latest Alembic migration
        # has not been applied yet.
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20)")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN DEFAULT FALSE")
        )
        # Hotfix for Norms table updates
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS institution_id INTEGER"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS academic_year VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS course_id INTEGER"))
        await conn.execute(text("ALTER TABLE norms DROP COLUMN IF EXISTS level"))
        await conn.execute(text("ALTER TABLE norms DROP COLUMN IF EXISTS ratio"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS faculty_student_ratio FLOAT"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS min_qualification VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS norm_type VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS course_category VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS grade_requirement VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS max_age INTEGER DEFAULT 38"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS workload_hours_per_week INTEGER DEFAULT 18"))
        await conn.execute(text("ALTER TABLE norms DROP COLUMN IF EXISTS practical_to_theory_ratio"))
        await conn.execute(text("ALTER TABLE existing_faculty ADD COLUMN IF NOT EXISTS date_of_birth DATE"))
        
        # Hotfix for Applications
        await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS cover_letter TEXT"))
        
        # Hotfix for Candidate registration
        await conn.execute(text("ALTER TABLE candidates ALTER COLUMN date_of_birth DROP NOT NULL"))
    yield



from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="CHB Portal Backend",
    description="Backend API for the Clock Hour Basis (CHB) Portal",
    version="1.0.0",
    lifespan=lifespan
)

uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

cors_origins_raw = settings.CORS_ORIGINS.strip('"').strip("'")
cors_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
# We don't strip '*' here so it can be used in allow_origins if desired,
# though allow_credentials=True will still require specific origins or regex.

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    """
    Catch SQLAlchemy IntegrityErrors (Unique constraints, etc.)
    """
    error_msg = str(exc.orig)
    detail = "Database integrity violation"
    
    if "unique constraint" in error_msg.lower():
        detail = "Duplicate entry detected. This record already exists."
    elif "foreign key constraint" in error_msg.lower():
        detail = "Referential integrity error: Related record not found."
        
    return JSONResponse(
        status_code=400,
        content={"status": "error", "code": "INTEGRITY_ERROR", "message": detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Normalize HTTPException payloads to the standard API error envelope.
    """
    code = "HTTP_ERROR"
    message = "Request failed"

    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", code)
        message = exc.detail.get("message", message)
    elif isinstance(exc.detail, str):
        message = exc.detail

    response = JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "code": code, "message": message},
    )
    origin = request.headers.get("origin")
    if origin and (origin in cors_origins or "*" in cors_origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(ResponseValidationError)
async def validation_exception_handler(request: Request, exc: ResponseValidationError):
    import traceback
    with open("D:/chb2/CHB/backend/scratch/response_error.log", "a") as f:
        f.write(f"\n--- ResponseValidationError ---\n")
        f.write(str(exc.errors()))
        f.write("\n")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.errors()},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch all unexpected errors and hide internal details from the user.
    """
    import traceback
    error_detail = traceback.format_exc()
    print(f"CRITICAL ERROR: {str(exc)}\n{error_detail}") 
    
    # Log to a file for easier debugging
    with open("backend_error.log", "a") as f:
        f.write(f"\n--- {datetime.now()} ---\n")
        f.write(error_detail)
        f.write("\n")

    response = JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": f"An unexpected internal error occurred: {str(exc)}",
        },
    )
    # Manual CORS header injection as fallback for exception handlers
    origin = request.headers.get("origin")
    if origin and (origin in cors_origins or "*" in cors_origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

app.include_router(auth_router, prefix="/api")
app.include_router(req_router, prefix="/api")
app.include_router(vacancy_router, prefix="/api")
app.include_router(ad_router, prefix="/api")
app.include_router(candidate_router, prefix="/api")
app.include_router(app_router, prefix="/api")
app.include_router(selection_router, prefix="/api")
app.include_router(weight_router, prefix="/api")
app.include_router(appointment_router, prefix="/api")
app.include_router(attendance_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(principal_router, prefix="/api")
app.include_router(helpdesk_router, prefix="/api")

from app.api.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/requirements")

@app.get("/")
async def read_root():
    return {"message": "Welcome to the CHB Portal API"}
