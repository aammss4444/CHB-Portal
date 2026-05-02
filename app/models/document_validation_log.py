import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class DocumentValidationLog(Base):
    __tablename__ = "document_validation_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("application_documents.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    check_type = Column(String(100), nullable=True)
    result = Column(String(20), nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("ApplicationDocument", back_populates="validation_logs")
