from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class IntakeDefinition(Base):
    __tablename__ = "intake_definitions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    academic_year = Column(String, nullable=False)  # e.g., "2026-2027"
    approved_seats = Column(Integer, nullable=False)
    actual_admitted = Column(Integer, nullable=False)

    course = relationship("Course", back_populates="intakes")
    faculty_requirements = relationship("FacultyRequirement", back_populates="intake", cascade="all, delete-orphan", passive_deletes=True)
