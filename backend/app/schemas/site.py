import uuid
from pydantic import BaseModel
from app.models import Jurisdiction


class SiteResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    polygon_geojson: dict
    jurisdiction: Jurisdiction

    model_config = {"from_attributes": True}