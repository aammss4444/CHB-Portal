import enum
from sqlalchemy import Boolean, Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    PRINCIPAL = "PRINCIPAL"
    CANDIDATE = "CANDIDATE"
    FACULTY = "FACULTY"
    RO = "RO"
    DIRECTORATE = "DIRECTORATE"
    TREASURY = "TREASURY"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    full_name = Column(String, nullable=True)
    phone_number = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    force_password_change = Column(Boolean, nullable=False, default=False)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True)

    institution = relationship("Institution")

    @property
    def permissions(self) -> list[str]:
        from app.core.permissions import get_permissions_for_role
        return get_permissions_for_role(self.role)
