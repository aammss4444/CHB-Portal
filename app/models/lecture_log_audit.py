import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class LectureLogAuditAction(str, enum.Enum):
    CREATED = "CREATED"
    EDITED = "EDITED"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"


class LectureLogAudit(Base):
    __tablename__ = "lecture_log_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lecture_log_id = Column(UUID(as_uuid=True), ForeignKey("lecture_logs.id"), nullable=False)
    action = Column(Enum(LectureLogAuditAction, name="lecture_log_audit_action_enum", create_type=False), nullable=False)
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
