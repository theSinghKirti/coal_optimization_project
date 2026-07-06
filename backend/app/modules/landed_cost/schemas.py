import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LandedCostCreate(BaseModel):
    plant_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    basic_cost: float = Field(ge=0)
    freight: float = Field(ge=0)
    taxes: float = Field(ge=0)
    other_cost: float = Field(default=0, ge=0)
    effective_from: date
    effective_to: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_effective_range(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from.")
        return self


class LandedCostUpdate(BaseModel):
    effective_to: date | None = None
    is_active: bool | None = None


class LandedCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    supplier_id: uuid.UUID | None
    document_id: uuid.UUID | None
    basic_cost: float
    freight: float
    taxes: float
    other_cost: float
    total_landed_cost: float
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
