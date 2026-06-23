import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Time, UniqueConstraint, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class TimetableLectureType(str, enum.Enum):
    THEORY = "THEORY"
    LAB = "LAB"
    TUTORIAL = "TUTORIAL"


class TimetableSlot(Base):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "course_id",
            "faculty_credential_id",
            "calendar_date",
            "slot_number",
            "academic_year",
            name="uq_timetable_faculty_slot_date_year",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    faculty_credential_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    calendar_date = Column(Date, nullable=False)
    slot_number = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    subject_name = Column(String(255), nullable=False)
    lecture_type = Column(Enum(TimetableLectureType, name="timetable_lecture_type_enum", create_type=False), nullable=False)
    class_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
