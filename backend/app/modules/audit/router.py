import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.audit import repository
from app.modules.audit.schemas import AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=Page[AuditLogRead])
def list_audit_logs(
    entity_type: str | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = repository.list_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)
