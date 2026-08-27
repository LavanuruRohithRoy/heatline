import uuid
import enum
from sqlalchemy import String, Float, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class MetricType(str, enum.Enum):
    HEAT_INDEX = "heat_index"
    DRY_BULB_TEMPERATURE = "dry_bulb_temperature"


class ThresholdRule(Base):
    """Static, seeded reference table — not user-editable."""
    __tablename__ = "threshold_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_type: Mapped[MetricType] = mapped_column(SAEnum(MetricType), nullable=False)
    heat_index_threshold_f: Mapped[float] = mapped_column(Float, nullable=True)  # null for non-threshold rules (UAE)
    mandated_action: Mapped[str] = mapped_column(String(255), nullable=False)
    citation: Mapped[str] = mapped_column(String(500), nullable=False)