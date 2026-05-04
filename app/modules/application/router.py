from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.application.controller import ApplicationController
from app.modules.application.schemas import (
    ApplicationCreateRequest,
    ApplicationSubmitRequest,
    ApplicationActionRequest,
    ApplicationAISummaryEnvelope,
    ApplicationAIAnalyzeEnvelope,
)
from app.dependencies.pagination import PaginationParams


router = APIRouter(tags=["Application Management (Step 4)"])
controller = ApplicationController()

candidate_only = RoleChecker([RoleEnum.CANDIDATE])
principal_or_admin = RoleChecker([RoleEnum.PRINCIPAL, RoleEnum.ADMIN])
candidate_or_principal = RoleChecker([RoleEnum.CANDIDATE, RoleEnum.PRINCIPAL])


@router.post("/applications", status_code=status.HTTP_201_CREATED, dependencies=[Depends(candidate_only)])
async def create_application(
    req: ApplicationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.create_application(db, current_user, req)


@router.post("/applications/{application_id}/documents", dependencies=[Depends(candidate_only)])
async def upload_documents(
    application_id: UUID,
    background_tasks: BackgroundTasks,
    documents: List[UploadFile] = File(...),
    document_type: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.upload_documents_bulk(
        db,
        current_user,
        application_id,
        documents,
        background_tasks,
        document_type=document_type,
    )


@router.get("/applications/{application_id}/ai-summary", response_model=ApplicationAISummaryEnvelope, dependencies=[Depends(principal_or_admin)])
async def get_application_ai_summary(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a summary of AI document scrutiny. Principal/Admin only."""
    return await controller.get_application_ai_summary(db, application_id, current_user)


@router.post("/applications/{application_id}/analyze-ai", response_model=ApplicationAIAnalyzeEnvelope, dependencies=[Depends(principal_or_admin)])
async def analyze_application_ai(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.analyze_application_ai(db, application_id, current_user)


@router.get("/applications/{application_id}/documents", dependencies=[Depends(candidate_or_principal)])
async def list_documents(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_documents(db, current_user, application_id)


@router.post("/applications/{application_id}/submit", dependencies=[Depends(candidate_only)])
async def submit_application(
    application_id: UUID,
    req: ApplicationSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.submit_application(db, current_user, application_id, req)


@router.post("/applications/{application_id}/action", dependencies=[Depends(principal_or_admin)])
async def process_application_action(
    application_id: UUID,
    req: ApplicationActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.process_application_action(db, current_user, application_id, req)


@router.delete("/applications/{application_id}/withdraw", dependencies=[Depends(candidate_only)])
async def withdraw_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.withdraw_application(db, current_user, application_id)


@router.get("/applications/my", dependencies=[Depends(candidate_only)])
async def list_my_applications(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_my_applications(db, current_user, pagination.skip, pagination.limit)


@router.get("/applications", dependencies=[Depends(principal_or_admin)])
async def list_applications(
    pagination: PaginationParams = Depends(),
    advertisement_id: UUID | None = Query(None),
    status: str | None = Query(None),
    course_id: int | None = Query(None),
    academic_year: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_applications(
        db,
        current_user,
        advertisement_id,
        status,
        course_id,
        academic_year,
        pagination.skip,
        pagination.limit,
    )
