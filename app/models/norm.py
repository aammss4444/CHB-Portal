from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class Norm(Base):
    __tablename__ = "norms"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    academic_year = Column(String, nullable=True) # e.g., "2026-27"
    norm_type = Column(String(20), nullable=False, default="GENERAL") # COURSE_WISE / GENERAL
    course_category = Column(String(100), nullable=True)
    faculty_student_ratio = Column(Float, nullable=False) # e.g., 20.0
    min_qualification = Column(String(255), nullable=False, server_default="")
    grade_requirement = Column(String(100), nullable=False, server_default="")
    max_age = Column(Integer, default=38)
    workload_hours_per_week = Column(Integer, default=18)


    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
