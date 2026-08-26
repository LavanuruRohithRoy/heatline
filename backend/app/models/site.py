import uuid
import enum
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Jurisdiction(str, enum.Enum):
    OSHA_FEDERAL = "osha_federal"
    CAL_OSHA = "cal_osha"
    UAE = "uae"

class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Full GeoJSON Polygon feature — same shape FortyGuard's polygon_aoi expects, no transform needed at call time
    polygon_geojson: Mapped[dict] = mapped_column(JSONB, nullable=False)
    jurisdiction: Mapped[Jurisdiction] = mapped_column(SAEnum(Jurisdiction), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="sites")
    shift_windows: Mapped[list["ShiftWindow"]] = relationship(back_populates="site")
    compliance_checks: Mapped[list["ComplianceCheck"]] = relationship(back_populates="site")