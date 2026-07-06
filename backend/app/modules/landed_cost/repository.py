import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.landed_cost.models import LandedCost


def create(db: Session, **kwargs) -> LandedCost:
    record = LandedCost(**kwargs)
    db.add(record)
    db.flush()
    return record


def get(db: Session, record_id: uuid.UUID) -> LandedCost | None:
    return db.get(LandedCost, record_id)


def list_records(
    db: Session,
    *,
    plant_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(LandedCost)
    count_stmt = select(func.count()).select_from(LandedCost)

    conditions = []
    if plant_id:
        conditions.append(LandedCost.plant_id == plant_id)
    if is_active is not None:
        conditions.append(LandedCost.is_active == is_active)

    for c in conditions:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(LandedCost.effective_from.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def list_active_for_plant(db: Session, plant_id: uuid.UUID, *, as_of: date) -> list[LandedCost]:
    stmt = select(LandedCost).where(
        LandedCost.plant_id == plant_id,
        LandedCost.is_active.is_(True),
        LandedCost.effective_from <= as_of,
        (LandedCost.effective_to.is_(None)) | (LandedCost.effective_to >= as_of),
    )
    return list(db.execute(stmt).scalars().all())
