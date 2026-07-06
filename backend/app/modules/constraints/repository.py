import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.constraints.models import FSAConstraint


def create(db: Session, **kwargs) -> FSAConstraint:
    record = FSAConstraint(**kwargs)
    db.add(record)
    db.flush()
    return record


def get(db: Session, record_id: uuid.UUID) -> FSAConstraint | None:
    return db.get(FSAConstraint, record_id)


def list_records(
    db: Session,
    *,
    plant_id: uuid.UUID | None = None,
    constraint_type: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(FSAConstraint)
    count_stmt = select(func.count()).select_from(FSAConstraint)

    conditions = []
    if plant_id:
        conditions.append(FSAConstraint.plant_id == plant_id)
    if constraint_type:
        conditions.append(FSAConstraint.constraint_type == constraint_type)
    if is_active is not None:
        conditions.append(FSAConstraint.is_active == is_active)

    for c in conditions:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(FSAConstraint.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def list_active_for_plant(db: Session, plant_id: uuid.UUID, *, as_of: date) -> list[FSAConstraint]:
    stmt = select(FSAConstraint).where(
        FSAConstraint.plant_id == plant_id,
        FSAConstraint.is_active.is_(True),
        FSAConstraint.contract_start_date <= as_of,
        FSAConstraint.contract_end_date >= as_of,
    )
    return list(db.execute(stmt).scalars().all())
