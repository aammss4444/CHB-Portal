import enum
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class CHBDesignation(str, enum.Enum):
    ASSISTANT_PROFESSOR = "ASSISTANT_PROFESSOR"
    ASSOCIATE_PROFESSOR = "ASSOCIATE_PROFESSOR"
    PROFESSOR = "PROFESSOR"
    VISITING_FACULTY = "VISITING_FACULTY"
    GUEST_FACULTY = "GUEST_FACULTY"


class RateLectureType(str, enum.Enum):
    THEORY = "THEORY"
    LAB = "LAB"
    TUTORIAL = "TUTORIAL"


class RateMaster(Base):
    __tablename__ = "rate_master"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "academic_year",
            "designation",
            "lecture_type",
            "effective_from",
            name="uq_rate_master_institution_year_designation_type_effective_from",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    designation = Column(Enum(CHBDesignation, name="chb_designation_enum", create_type=False), nullable=False)
    lecture_type = Column(Enum(RateLectureType, name="rate_lecture_type_enum", create_type=False), nullable=False)
    rate_per_lecture = Column(Numeric(10, 2), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
