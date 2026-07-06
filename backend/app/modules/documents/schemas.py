import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentType = Literal[
    "FSA",
    "BRIDGE_LINKAGE",
    "LANDED_COST",
    "IPP_RULES",
    "GOVERNMENT_ORDER",
    "VARIABLE_COST_PDF",
    "OTHER",
]


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: str
    original_filename: str
    sha256_hash: str
    plant_id: uuid.UUID | None
    needs_review: bool
    review_status: str
    notes: str | None
    created_at: datetime


class VariableCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID | None
    document_id: uuid.UUID
    source_plant_name: str
    effective_date: date | None
    variable_cost_per_unit: float
    unit: str
    needs_review: bool
    created_at: datetime


class VariableCostReviewUpdate(BaseModel):
    plant_id: uuid.UUID = Field(description="Plant to attach this row to after manual review")
    needs_review: bool = False


class VariableCostUploadResult(BaseModel):
    document: DocumentRead
    parsed_rows: list[VariableCostRead]
    rows_needing_review: int
    parser_notes: list[str]
