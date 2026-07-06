import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID | None
    plant_id: uuid.UUID | None
    recommendation_type: str
    severity: str
    message: str
    created_at: datetime
