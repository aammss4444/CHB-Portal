import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class CalendarDayType(str, enum.Enum):
    WORKING = "WORKING"
    HOLIDAY = "HOLIDAY"
    EXAM = "EXAM"
    HALF_DAY = "HALF_DAY"
    COMPENSATORY = "COMPENSATORY"


class AcademicCalendar(Base):
    __tablename__ = "academic_calendar"
    __table_args__ = (
        UniqueConstraint("institution_id", "calendar_date", "academic_year", name="uq_calendar_date_institution_year"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    calendar_date = Column(Date, nullable=False)
    day_type = Column(Enum(CalendarDayType, name="calendar_day_type_enum", create_type=False), nullable=False)
    description = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
