import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RunStatus = Literal["completed", "incomplete_data", "failed"]
TriggerSource = Literal["manual", "scheduler"]


class OptimizationRunRequest(BaseModel):
    triggered_by: TriggerSource = "manual"
    plant_ids: list[uuid.UUID] | None = None  # None = all active plants


class AllocationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    plant_id: uuid.UUID
    supplier_id: uuid.UUID | None
    allocation_type: str
    quantity_mt: float
    unit_cost: float
    estimated_cost: float
    acq_utilization_pct: float | None


class OptimizationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_timestamp: datetime
    status: str
    triggered_by: str
    solver_status: str | None
    total_estimated_cost: float | None
    notes: str | None


class OptimizationRunDetail(OptimizationRunRead):
    allocations: list[AllocationResultRead]
