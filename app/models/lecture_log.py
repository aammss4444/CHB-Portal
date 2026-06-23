import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Float,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class LectureLogType(str, enum.Enum):
    THEORY = "THEORY"
    LAB = "LAB"
    TUTORIAL = "TUTORIAL"
    SUBSTITUTE = "SUBSTITUTE"
    EXTRA = "EXTRA"


class LectureLogStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class LectureLog(Base):
    __tablename__ = "lecture_logs"
    __table_args__ = (
        UniqueConstraint(
            "faculty_credential_id",
            "lecture_date",
            "slot_number",
            name="uq_lecture_log_faculty_date_slot",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_credential_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=False)
    timetable_slot_id = Column(UUID(as_uuid=True), ForeignKey("timetable_slots.id"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    lecture_date = Column(Date, nullable=False)
    slot_number = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    subject_name = Column(String(255), nullable=False)
    lecture_type = Column(Enum(LectureLogType, name="lecture_log_type_enum", create_type=False), nullable=False)
    class_name = Column(String(100), nullable=True)
    topic_covered = Column(Text, nullable=False)
    attendance_count = Column(Integer, nullable=True)
    ai_attendance_count = Column(Integer, nullable=True)
    manual_attendance_count = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_extra = Column(Boolean, nullable=False, default=False)
    is_substitute = Column(Boolean, nullable=False, default=False)
    substitute_for_faculty_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=True)
    log_status = Column(Enum(LectureLogStatus, name="lecture_log_status_enum", create_type=False), nullable=False, default=LectureLogStatus.DRAFT.value)
    rejection_reason = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
