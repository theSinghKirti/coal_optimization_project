import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DailyStockCreate(BaseModel):
    plant_id: uuid.UUID
    report_date: date
    opening_stock_mt: float = Field(ge=0)
    receipt_mt: float = Field(ge=0)
    consumption_mt: float = Field(ge=0)
    closing_stock_mt: float = Field(ge=0)
    remarks: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reject_negative(self):
        # Field(ge=0) already rejects negatives; this guards against future refactors
        # where fields might be widened, keeping the "reject negative values" rule explicit.
        for name in ("opening_stock_mt", "receipt_mt", "consumption_mt", "closing_stock_mt"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative.")
        return self


class DailyStockUpdate(BaseModel):
    opening_stock_mt: float | None = Field(default=None, ge=0)
    receipt_mt: float | None = Field(default=None, ge=0)
    consumption_mt: float | None = Field(default=None, ge=0)
    closing_stock_mt: float | None = Field(default=None, ge=0)
    remarks: str | None = Field(default=None, max_length=1000)


class DailyStockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    report_date: date
    opening_stock_mt: float
    receipt_mt: float
    consumption_mt: float
    closing_stock_mt: float
    expected_closing_stock_mt: float
    reconciliation_difference_mt: float
    validation_status: str
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class LatestStockSummaryItem(BaseModel):
    plant_id: uuid.UUID
    plant_code: str
    plant_name: str
    report_date: date | None
    closing_stock_mt: float | None
    consumption_mt: float | None
    stock_days: float | None
    validation_status: str | None
