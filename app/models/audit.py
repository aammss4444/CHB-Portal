from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_name = Column(String, nullable=False) # e.g., "IntakeDefinition"
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False) # e.g., "CREATE", "UPDATE", "APPROVE"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
