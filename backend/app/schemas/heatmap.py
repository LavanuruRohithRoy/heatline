import uuid
from typing import Optional
from pydantic import BaseModel


class HeatmapTileDiagnostics(BaseModel):
    """Tile-distribution statistics for the most-recently fetched heatmap.

    All temperatures are in °F (same unit the API surfaces to callers).
    This object is purely informational — it has no effect on compliance
    decisions and is not persisted anywhere.
    """
    tile_count: int
    min_temp_f: float
    max_temp_f: float
    mean_temp_f: float
    median_temp_f: float


class HeatmapTile(BaseModel):
    geometry: dict
    temp_f: float


class HeatmapTilesResponse(BaseModel):
    site_id: uuid.UUID
    metric_label: str
    tiles: list[HeatmapTile]
    # Additive — existing callers that ignore extra fields are unaffected.
    diagnostics: Optional[HeatmapTileDiagnostics] = None
