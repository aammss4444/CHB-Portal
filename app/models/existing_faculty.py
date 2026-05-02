import uuid
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class ExistingFaculty(Base):
    __tablename__ = "existing_faculty"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    employee_id = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=False)
    designation = Column(String(100), nullable=False) # Professor, Associate Professor, Assistant Professor
    employment_type = Column(String(50), nullable=False) # PERMANENT, CONTRACT, DEPUTED_IN
    qualification = Column(String(100))
    specialization = Column(String(100))
    date_of_birth = Column(Date, nullable=True)
    date_of_joining = Column(Date, nullable=False)
    status = Column(String(50), default="ACTIVE") # ACTIVE, ON_LEAVE, DEPUTED_OUT, RETIRED
    is_effective = Column(Boolean, default=True)
    academic_year = Column(String(20), nullable=False)
    
    entered_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('institution_id', 'employee_id', 'academic_year', name='_inst_employee_year_uc'),
    )

    qualifications_list = relationship("FacultyQualification", back_populates="faculty", cascade="all, delete-orphan")
