import uuid
import enum
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    HSE_MANAGER = "hse_manager"
    VIEWER = "viewer"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.VIEWER)

    organization: Mapped["Organization"] = relationship(back_populates="users")