import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConstraintType = Literal["FSA", "BRIDGE_LINKAGE"]


class FSAConstraintCreate(BaseModel):
    constraint_type: ConstraintType = "FSA"
    plant_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    coal_company_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    annual_contract_quantity_mt: float | None = Field(default=None, ge=0)
    monthly_cap_mt: float | None = Field(default=None, ge=0)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    is_active: bool = True

    # New columns
    fiscal_year: str | None = None
    raw_source_name: str | None = None
    coal_company: str | None = None
    quantity_lac_mt: float | None = Field(default=None, ge=0)
    quantity_mt: float | None = Field(default=None, ge=0)
    valid_to: date | None = None
    remarks: str | None = None
    extraction_confidence: float | None = None
    parser_notes: str | None = None
    status: str = "PENDING_REVIEW"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.contract_start_date and self.contract_end_date:
            if self.contract_end_date < self.contract_start_date:
                raise ValueError("contract_end_date cannot be earlier than contract_start_date.")
        return self


class FSAConstraintUpdate(BaseModel):
    monthly_cap_mt: float | None = Field(default=None, ge=0)
    contract_end_date: date | None = None
    is_active: bool | None = None


class FSAConstraintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    constraint_type: str
    plant_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    coal_company_id: uuid.UUID | None
    document_id: uuid.UUID | None
    annual_contract_quantity_mt: float | None
    monthly_cap_mt: float | None
    contract_start_date: date | None
    contract_end_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    fiscal_year: str | None
    raw_source_name: str | None
    coal_company: str | None
    quantity_lac_mt: float | None
    quantity_mt: float | None
    valid_to: date | None
    remarks: str | None
    extraction_confidence: float | None
    parser_notes: str | None
    status: str


class FSAConstraintReview(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    plant_id: uuid.UUID | None = None
    coal_company_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None

