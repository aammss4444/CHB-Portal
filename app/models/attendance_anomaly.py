import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class AnomalySeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AttendanceAnomaly(Base):
    __tablename__ = "attendance_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_credential_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=False)
    lecture_log_id = Column(UUID(as_uuid=True), ForeignKey("lecture_logs.id"), nullable=True)
    summary_id = Column(UUID(as_uuid=True), ForeignKey("daily_attendance_summary.id"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    anomaly_type = Column(String(100), nullable=False)
    severity = Column(Enum(AnomalySeverity, name="anomaly_severity_enum", create_type=False), nullable=False)
    description = Column(Text, nullable=False)
    is_acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledgement_remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
