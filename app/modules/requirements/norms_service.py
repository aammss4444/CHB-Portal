from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.norm import Norm


class NormResolutionError(Exception):
    pass


def derive_course_category(course_name: str, course_level: str) -> Optional[str]:
    src = f"{course_name} {course_level}".lower()

    if "hotel" in src or "hmct" in src:
        return "HMCT (Hotel Management)"
    if "physics" in src or "chemistry" in src or "math" in src or "applied" in src:
        return "Non-Engineering (Applied Sciences)"
    if "diploma" in src:
        return "Engineering & Technology (Diploma)"
    if any(token in src for token in ["degree", "ug", "b.e", "btech", "b.tech", "engineering", "pg"]):
        return "Engineering (Degree - B.E./B.Tech)"
    return None


async def resolve_norm(
    db: AsyncSession,
    academic_year: Optional[str],
    course_category: Optional[str],
) -> Norm:
    # Priority 1: course-wise norm
    if course_category:
        stmt = (
            select(Norm)
            .where(
                Norm.norm_type == "COURSE_WISE",
                Norm.course_category == course_category,
            )
            .order_by(Norm.id.desc())
        )
        if academic_year:
            stmt = stmt.where((Norm.academic_year == academic_year) | (Norm.academic_year.is_(None)))
        res = await db.execute(stmt)
        norm = res.scalars().first()
        if norm:
            return norm

    # Priority 2: general norm
    stmt = (
        select(Norm)
        .where(
            Norm.norm_type == "GENERAL",
        )
        .order_by(Norm.id.desc())
    )
    if academic_year:
        stmt = stmt.where((Norm.academic_year == academic_year) | (Norm.academic_year.is_(None)))
    res = await db.execute(stmt)
    norm = res.scalars().first()
    if norm:
        return norm

    # Priority 3: latest norm fallback
    legacy_stmt = select(Norm).order_by(Norm.id.desc())
    if academic_year:
        legacy_stmt = legacy_stmt.where((Norm.academic_year == academic_year) | (Norm.academic_year.is_(None)))
    legacy_res = await db.execute(legacy_stmt)
    legacy_norm = legacy_res.scalars().first()
    if legacy_norm:
        return legacy_norm

    raise NormResolutionError("No active norm found for requested context")
