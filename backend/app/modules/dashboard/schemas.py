import uuid

from pydantic import BaseModel


class DashboardPlantSnapshot(BaseModel):
    plant_id: uuid.UUID
    plant_code: str
    plant_name: str
    stock_days: float | None
    validation_status: str | None


class DashboardSummary(BaseModel):
    total_plants: int
    active_plants: int
    plants_with_warnings: int
    plants_missing_stock: int
    open_recommendations: int
    critical_recommendations: int
    latest_optimization_run_id: uuid.UUID | None
    latest_optimization_status: str | None
    latest_optimization_total_cost: float | None
    plant_snapshots: list[DashboardPlantSnapshot]
