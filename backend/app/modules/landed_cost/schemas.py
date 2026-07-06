import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LandedCostCreate(BaseModel):
    plant_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    basic_cost: float | None = Field(default=None, ge=0)
    freight: float | None = Field(default=None, ge=0)
    taxes: float | None = Field(default=None, ge=0)
    other_cost: float = Field(default=0, ge=0)
    total_landed_cost: float | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool = True

    raw_source_name: str | None = None
    weighted_avg_gcv_kcal_per_kg: float | None = None
    cost_basis: str = "CERTIFIED_WEIGHTED_AVERAGE"
    extraction_confidence: float | None = None
    parser_notes: str | None = None
    status: str = "APPROVED"
    needs_review: bool = False


    @model_validator(mode="after")
    def validate_effective_range(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from.")
        return self


class LandedCostUpdate(BaseModel):
    effective_to: date | None = None
    is_active: bool | None = None


class LandedCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    document_id: uuid.UUID | None
    basic_cost: float | None
    freight: float | None
    taxes: float | None
    other_cost: float | None
    total_landed_cost: float | None
    effective_from: date | None
    effective_to: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    raw_source_name: str | None
    weighted_avg_gcv_kcal_per_kg: float | None
    cost_basis: str
    extraction_confidence: float | None
    parser_notes: str | None
    status: str
    needs_review: bool

    # Virtual computed field to match API requirement
    total_landed_cost_rs_per_mt: float | None = None

    @model_validator(mode="after")
    def populate_rs_per_mt(self) -> "LandedCostRead":
        self.total_landed_cost_rs_per_mt = self.total_landed_cost
        return self


class LandedCostReview(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    plant_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None

