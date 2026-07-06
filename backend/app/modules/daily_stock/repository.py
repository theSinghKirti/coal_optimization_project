import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.daily_stock.models import DailyStock
from app.modules.master_data.models import Plant


def create(db: Session, **kwargs) -> DailyStock:
    record = DailyStock(**kwargs)
    db.add(record)
    db.flush()
    return record


def get(db: Session, record_id: uuid.UUID) -> DailyStock | None:
    return db.get(DailyStock, record_id)


def get_by_plant_and_date(db: Session, plant_id: uuid.UUID, report_date: date) -> DailyStock | None:
    return db.execute(
        select(DailyStock).where(DailyStock.plant_id == plant_id, DailyStock.report_date == report_date)
    ).scalar_one_or_none()


def list_records(
    db: Session,
    *,
    plant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    validation_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(DailyStock)
    count_stmt = select(func.count()).select_from(DailyStock)

    conditions = []
    if plant_id:
        conditions.append(DailyStock.plant_id == plant_id)
    if date_from:
        conditions.append(DailyStock.report_date >= date_from)
    if date_to:
        conditions.append(DailyStock.report_date <= date_to)
    if validation_status:
        conditions.append(DailyStock.validation_status == validation_status)

    for c in conditions:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(DailyStock.report_date.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def latest_per_active_plant(db: Session) -> list[tuple[Plant, DailyStock | None]]:
    """Returns each active plant paired with its most recent daily stock record (or None)."""
    plants = list(db.execute(select(Plant).where(Plant.is_active.is_(True))).scalars().all())
    results = []
    for plant in plants:
        latest = db.execute(
            select(DailyStock)
            .where(DailyStock.plant_id == plant.id)
            .order_by(DailyStock.report_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        results.append((plant, latest))
    return results
