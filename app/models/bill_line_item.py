import enum
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class BillLineLectureType(str, enum.Enum):
    THEORY = "THEORY"
    LAB = "LAB"
    TUTORIAL = "TUTORIAL"
    EXTRA = "EXTRA"
    SUBSTITUTE = "SUBSTITUTE"


class BillLineItem(Base):
    __tablename__ = "bill_line_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("chb_bill.id"), nullable=False)
    lecture_log_id = Column(UUID(as_uuid=True), ForeignKey("lecture_logs.id"), nullable=False)
    lecture_date = Column(Date, nullable=False)
    slot_number = Column(Integer, nullable=False)
    subject_name = Column(String(255), nullable=False)
    lecture_type = Column(Enum(BillLineLectureType, name="bill_line_lecture_type_enum", create_type=False), nullable=False)
    class_name = Column(String(100), nullable=True)
    rate_per_lecture = Column(Numeric(10, 2), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    is_extra = Column(Boolean, nullable=False, default=False)
    is_substitute = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
