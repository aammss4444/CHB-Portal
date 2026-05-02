import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class DailyAttendanceSummary(Base):
    __tablename__ = "daily_attendance_summary"
    __table_args__ = (
        UniqueConstraint("faculty_credential_id", "attendance_date", name="uq_daily_attendance_faculty_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_credential_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    attendance_date = Column(Date, nullable=False)
    scheduled_lectures = Column(Integer, nullable=False, default=0)
    conducted_lectures = Column(Integer, nullable=False, default=0)
    extra_lectures = Column(Integer, nullable=False, default=0)
    substitute_lectures = Column(Integer, nullable=False, default=0)
    total_billable_lectures = Column(Integer, nullable=False, default=0)
    is_present = Column(Boolean, nullable=False, default=False)
    is_holiday = Column(Boolean, nullable=False, default=False)
    is_locked = Column(Boolean, nullable=False, default=False)
    lock_reason = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
