import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.optimization.models import AllocationResult, OptimizationRun


def create_run(db: Session, **kwargs) -> OptimizationRun:
    run = OptimizationRun(**kwargs)
    db.add(run)
    db.flush()
    return run


def add_allocation(db: Session, **kwargs) -> AllocationResult:
    allocation = AllocationResult(**kwargs)
    db.add(allocation)
    return allocation


def get_run(db: Session, run_id: uuid.UUID) -> OptimizationRun | None:
    return db.execute(
        select(OptimizationRun)
        .options(selectinload(OptimizationRun.allocations))
        .where(OptimizationRun.id == run_id)
    ).scalar_one_or_none()


def list_runs(db: Session, *, limit: int = 50, offset: int = 0):
    from sqlalchemy import func

    total = db.execute(select(func.count()).select_from(OptimizationRun)).scalar_one()
    stmt = select(OptimizationRun).order_by(OptimizationRun.run_timestamp.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def get_latest_run(db: Session) -> OptimizationRun | None:
    stmt = (
        select(OptimizationRun)
        .options(selectinload(OptimizationRun.allocations))
        .order_by(OptimizationRun.run_timestamp.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
