import uuid
from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class ThresholdRule(Base):
    """Static, seeded reference table — not user-editable."""
    __tablename__ = "threshold_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    heat_index_threshold_f: Mapped[float] = mapped_column(Float, nullable=True)  # null for non-heat-index rules (UAE)
    mandated_action: Mapped[str] = mapped_column(String(255), nullable=False)
    citation: Mapped[str] = mapped_column(String(500), nullable=False)