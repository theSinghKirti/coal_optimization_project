import uuid
from datetime import date

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    category: str  # e.g. "missing_daily_stock", "expired_fsa_constraint", "stock_warning"
    severity: str  # "warning" | "critical"
    plant_id: uuid.UUID | None
    plant_code: str | None
    message: str
    reference_date: date | None = None


class ValidationSummary(BaseModel):
    generated_at: str
    total_issues: int
    issues: list[ValidationIssue]
