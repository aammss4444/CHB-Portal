from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.user import User, RoleEnum
from app.modules.principal.controller import PrincipalController
from app.modules.principal.schemas import PrincipalDashboardResponse

router = APIRouter(prefix="/principal", tags=["Principal Dashboard"])
controller = PrincipalController()

principal_only = RoleChecker([RoleEnum.PRINCIPAL])

@router.get("/dashboard", response_model=PrincipalDashboardResponse, dependencies=[Depends(principal_only)])
async def get_principal_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.get_dashboard_data(db, current_user)

@router.post("/institute/location", dependencies=[Depends(principal_only)])
async def set_institute_location(
    req: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.set_institute_location(db, current_user, req.get('latitude'), req.get('longitude'))
