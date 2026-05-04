from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class SelectionAISnapshot(Base):
    __tablename__ = "selection_ai_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    institution_id = Column(Integer, nullable=False)
    snapshot_data = Column(JSON, nullable=False)
    analysis_data = Column(JSON, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
