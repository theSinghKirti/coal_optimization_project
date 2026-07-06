import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConstraintType = Literal["FSA", "BRIDGE_LINKAGE"]


class FSAConstraintCreate(BaseModel):
    constraint_type: ConstraintType = "FSA"
    plant_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    coal_company_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    annual_contract_quantity_mt: float = Field(gt=0)
    monthly_cap_mt: float | None = Field(default=None, gt=0)
    contract_start_date: date
    contract_end_date: date
    is_active: bool = True

    @model_validator(mode="after")
    def validate_dates(self):
        if self.contract_end_date < self.contract_start_date:
            raise ValueError("contract_end_date cannot be earlier than contract_start_date.")
        return self


class FSAConstraintUpdate(BaseModel):
    monthly_cap_mt: float | None = Field(default=None, gt=0)
    contract_end_date: date | None = None
    is_active: bool | None = None


class FSAConstraintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    constraint_type: str
    plant_id: uuid.UUID
    supplier_id: uuid.UUID | None
    coal_company_id: uuid.UUID | None
    document_id: uuid.UUID | None
    annual_contract_quantity_mt: float
    monthly_cap_mt: float | None
    contract_start_date: date
    contract_end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime
