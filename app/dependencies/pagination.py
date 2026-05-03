import math
from typing import Any, TypeVar, Generic, Sequence
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.sql.selectable import Select

T = TypeVar('T')

class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(10, ge=1, le=100, description="Items per page")
    ):
        self.page = page
        self.limit = limit
        self.skip = (page - 1) * limit

async def paginate(db: AsyncSession, query: Select, params: PaginationParams) -> dict:
    """
    Executes a paginated query returning a dictionary matching the PaginatedResponse schema.
    """
    # Count total records
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch paginated records
    paginated_query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(paginated_query)
    data = result.scalars().all()

    total_pages = math.ceil(total / params.limit) if params.limit > 0 else 0

    return {
        "data": data,
        "total": total,
        "page": params.page,
        "limit": params.limit,
        "total_pages": total_pages
    }

def paginate_sync(db: Session, query: Select, params: PaginationParams) -> dict:
    """
    Synchronous version for non-async endpoints.
    """
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    paginated_query = query.offset(params.skip).limit(params.limit)
    data = db.execute(paginated_query).scalars().all()

    total_pages = math.ceil(total / params.limit) if params.limit > 0 else 0

    return {
        "data": data,
        "total": total,
        "page": params.page,
        "limit": params.limit,
        "total_pages": total_pages
    }
