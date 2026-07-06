"""Daily stock business rules: reconciliation math, warning/remarks enforcement.

Expected Closing Stock = Opening Stock + Receipt - Consumption
Reconciliation Difference = Entered Closing Stock - Expected Closing Stock
"""

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit import service as audit_service
from app.modules.daily_stock import repository
from app.modules.daily_stock.models import DailyStock
from app.modules.daily_stock.schemas import DailyStockCreate, DailyStockUpdate
from app.modules.master_data import repository as master_data_repository

settings = get_settings()


def _compute_reconciliation(opening: float, receipt: float, consumption: float, closing: float):
    expected_closing = opening + receipt - consumption
    difference = closing - expected_closing
    is_warning = abs(difference) > settings.stock_reconciliation_tolerance_mt
    return expected_closing, difference, is_warning


def create_daily_stock(db: Session, payload: DailyStockCreate) -> DailyStock:
    plant = master_data_repository.get_plant(db, payload.plant_id)
    if not plant:
        raise NotFoundError("Unknown plant: cannot record daily stock for a plant that does not exist.")

    if repository.get_by_plant_and_date(db, payload.plant_id, payload.report_date):
        raise ConflictError(
            f"A daily stock record already exists for plant '{plant.plant_code}' on {payload.report_date}."
        )

    expected_closing, difference, is_warning = _compute_reconciliation(
        payload.opening_stock_mt,
        payload.receipt_mt,
        payload.consumption_mt,
        payload.closing_stock_mt,
    )

    if is_warning and not (payload.remarks and payload.remarks.strip()):
        raise ValidationFailedError(
            "Reconciliation difference exceeds tolerance; remarks are mandatory for warning records."
        )

    record = repository.create(
        db,
        plant_id=payload.plant_id,
        report_date=payload.report_date,
        opening_stock_mt=payload.opening_stock_mt,
        receipt_mt=payload.receipt_mt,
        consumption_mt=payload.consumption_mt,
        closing_stock_mt=payload.closing_stock_mt,
        expected_closing_stock_mt=expected_closing,
        reconciliation_difference_mt=difference,
        validation_status="warning" if is_warning else "ok",
        remarks=payload.remarks,
    )

    audit_service.record(
        db,
        entity_type="daily_stock",
        entity_id=record.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return record


def update_daily_stock(db: Session, record_id: uuid.UUID, payload: DailyStockUpdate) -> DailyStock:
    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Daily stock record not found.")

    before = {
        "opening_stock_mt": float(record.opening_stock_mt),
        "receipt_mt": float(record.receipt_mt),
        "consumption_mt": float(record.consumption_mt),
        "closing_stock_mt": float(record.closing_stock_mt),
        "remarks": record.remarks,
    }

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)

    expected_closing, difference, is_warning = _compute_reconciliation(
        float(record.opening_stock_mt),
        float(record.receipt_mt),
        float(record.consumption_mt),
        float(record.closing_stock_mt),
    )

    if is_warning and not (record.remarks and record.remarks.strip()):
        raise ValidationFailedError(
            "Reconciliation difference exceeds tolerance; remarks are mandatory for warning records."
        )

    record.expected_closing_stock_mt = expected_closing
    record.reconciliation_difference_mt = difference
    record.validation_status = "warning" if is_warning else "ok"

    db.flush()
    audit_service.record(
        db,
        entity_type="daily_stock",
        entity_id=record.id,
        action="update",
        before=before,
        after=data,
    )
    return record


def get_or_404(db: Session, record_id: uuid.UUID) -> DailyStock:
    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Daily stock record not found.")
    return record


def list_daily_stock(db: Session, **filters):
    return repository.list_records(db, **filters)


def latest_summary(db: Session):
    """Latest stock position per active plant, with computed stock-days for recommendations."""
    rows = repository.latest_per_active_plant(db)
    summary = []
    for plant, record in rows:
        stock_days = None
        if record and float(record.consumption_mt) > 0:
            stock_days = float(record.closing_stock_mt) / float(record.consumption_mt)
        summary.append(
            {
                "plant_id": plant.id,
                "plant_code": plant.plant_code,
                "plant_name": plant.plant_name,
                "report_date": record.report_date if record else None,
                "closing_stock_mt": float(record.closing_stock_mt) if record else None,
                "consumption_mt": float(record.consumption_mt) if record else None,
                "stock_days": stock_days,
                "validation_status": record.validation_status if record else None,
            }
        )
    return summary
