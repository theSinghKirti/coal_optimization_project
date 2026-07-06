import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    actor: str
    before: dict | None
    after: dict | None
    note: str | None
    created_at: datetime
