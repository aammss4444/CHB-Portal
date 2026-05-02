import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class FacultyQualification(Base):
    __tablename__ = "faculty_qualifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("existing_faculty.id", ondelete="CASCADE"), nullable=False)
    degree = Column(String(100), nullable=False)
    specialization = Column(String(100))
    university = Column(String(255))
    year_of_passing = Column(Integer)
    is_highest = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    faculty = relationship("ExistingFaculty", back_populates="qualifications_list")
