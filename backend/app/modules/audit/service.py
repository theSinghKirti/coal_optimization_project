"""Audit logging helper used by every other module.

Every write path that mutates business data or runs optimization should call
`record` so the platform keeps a complete, queryable history of changes.
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def record(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    actor: str = "system",
    note: str | None = None,
) -> AuditLog:
    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        before=before,
        after=after,
        note=note,
    )
    db.add(log)
    return log
