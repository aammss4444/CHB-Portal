import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class PublishedAdvertisement(Base):
    __tablename__ = "published_advertisements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), unique=True, nullable=False)
    public_token = Column(String(100), unique=True, nullable=False)
    published_by = Column(Integer, ForeignKey("users.id"))
    published_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    advertisement = relationship("Advertisement", back_populates="publication")
