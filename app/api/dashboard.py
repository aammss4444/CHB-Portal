from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.api.auth import get_current_user, RoleChecker
from app.models.user import RoleEnum

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

admin_or_ro = RoleChecker([RoleEnum.ADMIN, RoleEnum.RO])

@router.get("/admin-stats", dependencies=[Depends(admin_or_ro)])
async def get_admin_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """
    Fetch live statistics for the Admin Dashboard overview cards.
    """
    query = text("""
        SELECT
            (SELECT COUNT(*) FROM advertisements) as ads_count,
            (SELECT COUNT(*) FROM vacancy_assessments) as vacancy_count,
            (SELECT COUNT(*) FROM users) as users_count,
            (SELECT COUNT(*) FROM chb_bill WHERE bill_status = 'TREASURY_PROCESSED') as bills_count
    """)
    result = await db.execute(query)
    row = result.fetchone()
    
    return {
        "status": "success",
        "data": {
            "advertisements": row.ads_count if row else 0,
            "vacancies": row.vacancy_count if row else 0,
            "users": row.users_count if row else 0,
            "bills": row.bills_count if row else 0,
        }
    }

@router.get("/ro-stats", dependencies=[Depends(RoleChecker([RoleEnum.RO]))])
async def get_ro_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """
    Fetch live statistics for the RO Dashboard overview cards.
    """
    query = text("""
        SELECT
            (SELECT COUNT(*) FROM institutions) as institutes_count,
            (SELECT COUNT(*) FROM advertisements WHERE status = 'PUBLISHED') as verified_ads_count,
            (SELECT COUNT(*) FROM advertisements WHERE status = 'REVIEW') as pending_approvals_count
    """)
    result = await db.execute(query)
    row = result.fetchone()
    
    return {
        "status": "success",
        "data": {
            "institutes": row.institutes_count if row else 0,
            "verifiedAds": row.verified_ads_count if row else 0,
            "pendingApprovals": row.pending_approvals_count if row else 0,
        }
    }
