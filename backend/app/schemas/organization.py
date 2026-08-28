import uuid
from pydantic import BaseModel
from app.models import Plan


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    plan: Plan
    is_public_demo: bool

    model_config = {"from_attributes": True}