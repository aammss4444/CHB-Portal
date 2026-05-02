import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class AdvertisementAudit(Base):
    __tablename__ = "advertisement_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    action = Column(String(50), nullable=False) # GENERATED, EDITED, SUBMITTED, APPROVED, REJECTED, PUBLISHED
    performed_by = Column(Integer, ForeignKey("users.id"))
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    advertisement = relationship("Advertisement", back_populates="audit_trail")
