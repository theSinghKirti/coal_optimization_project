import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.recommendations.models import Recommendation


def create(db: Session, **kwargs) -> Recommendation:
    rec = Recommendation(**kwargs)
    db.add(rec)
    return rec


def list_recommendations(
    db: Session,
    *,
    plant_id: uuid.UUID | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(Recommendation)
    count_stmt = select(func.count()).select_from(Recommendation)
    if plant_id:
        stmt = stmt.where(Recommendation.plant_id == plant_id)
        count_stmt = count_stmt.where(Recommendation.plant_id == plant_id)
    if severity:
        stmt = stmt.where(Recommendation.severity == severity)
        count_stmt = count_stmt.where(Recommendation.severity == severity)
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Recommendation.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total
