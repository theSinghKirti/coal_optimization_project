import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def list_logs(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditLog.entity_id == entity_id)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    items = list(db.execute(stmt).scalars().all())
    return items, total
