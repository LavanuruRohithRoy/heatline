import uuid
from pydantic import BaseModel


class HeatmapTile(BaseModel):
    geometry: dict
    temp_f: float


class HeatmapTilesResponse(BaseModel):
    site_id: uuid.UUID
    metric_label: str
    tiles: list[HeatmapTile]
