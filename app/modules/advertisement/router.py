from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.advertisement.controller import AdvertisementController
from app.modules.advertisement.schemas import (
    AdvertisementApproveRequest,
    AdvertisementEnvelope,
    AdvertisementGenerateRequest,
    AdvertisementUpdateRequest,
    PublicAdvertisementEnvelope,
    PublishEnvelope,
    PublishedAdvertisementListEnvelope,
    AIAdvertisementGenerationEnvelope,
    AdvertisementMetaEnvelope,
    AdvertisementAIGenerateEnvelope,
)
from app.schemas.advertisement_ai import AdvertisementAIRequest
from app.dependencies.pagination import PaginationParams

router = APIRouter(prefix="/advertisements", tags=["Advertisement Creation (Step 3)"])
controller = AdvertisementController()

principal_only = RoleChecker([RoleEnum.PRINCIPAL])
admin_only = RoleChecker([RoleEnum.ADMIN])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])


@router.get("/", dependencies=[Depends(admin_or_principal)])
async def list_advertisements(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_advertisements(db, current_user, pagination.skip, pagination.limit)


@router.post(
    "/generate",
    response_model=AdvertisementEnvelope,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_or_principal)],
)
async def generate_advertisement(
    req: AdvertisementGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.generate_advertisement(db, current_user, req)


@router.get("/published") # Return type changed to raw dict in controller, so removing strict response_model constraint for now or it will fail
async def list_published_advertisements(
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all currently published advertisements. Accessible to anyone."""
    return await controller.list_published_advertisements(db, institution_id, course_id, academic_year, pagination.skip, pagination.limit)


@router.get("/meta", response_model=AdvertisementMetaEnvelope, dependencies=[Depends(admin_or_principal)])
async def get_advertisement_meta(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_advertisement_meta(db, current_user)


@router.post(
    "/generate-ai",
    response_model=AdvertisementAIGenerateEnvelope,
    dependencies=[Depends(admin_or_principal)],
)
async def generate_advertisement_ai(
    req: AdvertisementAIRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.generate_advertisement_ai(db, current_user, req)


@router.get(
    "/recruitment-context",
    dependencies=[Depends(admin_or_principal)],
    summary="Fetch linked Step 1 + Step 2 data for ad generation context",
)
async def get_recruitment_context(
    institution_id: int,
    course_id: int,
    academic_year: str = "2026-27",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns institution, course, norms, faculty requirement (Step 1), 
    and vacancy assessment (Step 2) data for the ad generation dashboard.
    """
    return await controller.get_recruitment_context(db, current_user, institution_id, course_id, academic_year)


@router.get("/{advertisement_id}", response_model=AdvertisementEnvelope, dependencies=[Depends(admin_or_principal)])
async def get_advertisement(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_advertisement(db, advertisement_id, current_user)


@router.put("/{advertisement_id}", response_model=AdvertisementEnvelope, dependencies=[Depends(admin_or_principal)])
async def update_advertisement(
    advertisement_id: UUID,
    req: AdvertisementUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.update_advertisement(db, advertisement_id, current_user, req)


@router.post("/{advertisement_id}/submit", response_model=AdvertisementEnvelope, dependencies=[Depends(admin_or_principal)])
async def submit_advertisement(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.submit_advertisement(db, advertisement_id, current_user)


@router.post("/{advertisement_id}/approve", response_model=AdvertisementEnvelope, dependencies=[Depends(admin_only)])
async def approve_advertisement(
    advertisement_id: UUID,
    req: AdvertisementApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.approve_advertisement(db, advertisement_id, current_user, req)


@router.post("/{advertisement_id}/publish", response_model=PublishEnvelope, dependencies=[Depends(admin_only)])
async def publish_advertisement(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.publish_advertisement(db, advertisement_id, current_user)


@router.delete("/{advertisement_id}", dependencies=[Depends(admin_or_principal)])
async def delete_advertisement(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.delete_advertisement(db, advertisement_id, current_user)


@router.get("/public/{public_token}", response_model=PublicAdvertisementEnvelope)
async def get_public_advertisement(
    public_token: str,
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_public_advertisement(db, public_token)
