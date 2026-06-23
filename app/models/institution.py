from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.db.session import Base


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    district = Column(String, nullable=False)
    type = Column(String, nullable=False)  # e.g., Govt, Aided, Unaided
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    courses = relationship("Course", back_populates="institution", cascade="all, delete-orphan", passive_deletes=True)


class Course(Base):
    """
    Represents a course offered by an institution.
    e.g., Computer Engineering (Diploma), Pharmacy (D.Pharm), etc.
    Replaces the old Branch model — the DB table is 'courses'.
    """
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)   # e.g., Computer Engineering
    level = Column(String, nullable=False)  # e.g., Diploma, Degree, D.Pharm

    institution = relationship("Institution", back_populates="courses")
    intakes = relationship("IntakeDefinition", back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
