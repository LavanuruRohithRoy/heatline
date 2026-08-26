import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, Float, Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    heat_index_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_breached: Mapped[bool] = mapped_column(Boolean, nullable=False)
    action_triggered: Mapped[str] = mapped_column(String(255), nullable=True)

    site: Mapped["Site"] = relationship(back_populates="compliance_checks")