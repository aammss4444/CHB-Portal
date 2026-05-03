import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    document_type = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)
    file_size_kb = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    is_required = Column(Boolean, nullable=False, default=False)
    validation_status = Column(String(30), nullable=False, default="PENDING")
    validation_message = Column(Text, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("Application", back_populates="documents")
    validation_logs = relationship(
        "DocumentValidationLog",
        back_populates="document",
        cascade="all, delete-orphan",
    )
