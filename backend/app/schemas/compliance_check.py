import uuid
from datetime import datetime
from pydantic import BaseModel


class ComplianceCheckResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    checked_at: datetime
    heat_index_value: float
    threshold_breached: bool
    action_triggered: str | None
    metric_label: str
    data_as_of: str
    threshold_value: float | None = None

    model_config = {"from_attributes": True}