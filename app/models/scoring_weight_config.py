import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Date, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class ScoringWeightConfig(Base):
    __tablename__ = "scoring_weight_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_name = Column(String(100), nullable=False)
    
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    level = Column(String(20), nullable=True) # UG, PG, DIPLOMA
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=True)
    
    qualification_weight = Column(Numeric(5, 2), nullable=False)
    experience_weight = Column(Numeric(5, 2), nullable=False)
    interview_weight = Column(Numeric(5, 2), nullable=False)
    publication_weight = Column(Numeric(5, 2), nullable=False)
    reservation_weight = Column(Numeric(5, 2), nullable=False)
    
    set_by_role = Column(String(30), nullable=False) # ADMIN, PRINCIPAL
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
