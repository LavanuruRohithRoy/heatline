import uuid
from datetime import time
from sqlalchemy import ForeignKey, Time, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class ShiftWindow(Base):
    __tablename__ = "shift_windows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_active: Mapped[str] = mapped_column(String(20), default="mon-fri")  # simple string, not overengineering this

    site: Mapped["Site"] = relationship(back_populates="shift_windows")